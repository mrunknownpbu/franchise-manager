import logging
from datetime import datetime, timedelta
from typing import Optional
import secrets
import hashlib
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.models import User, Session as SessionModel
from app.schemas import UserResponse
from app.config import get_settings

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Authentication service for user login and session management."""

    def __init__(self):
        self.settings = get_settings()
        self.session_timeout = timedelta(hours=self.settings.session_timeout_hours)

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)

    def login(self, db: Session, username: str, password: str) -> Optional[tuple[User, str]]:
        """Authenticate user and create session.
        
        Returns: (user, session_token) or None if authentication fails
        """
        logger.info(f"Login attempt for user: {username}")
        
        # Find user
        user = db.query(User).filter(User.username == username).first()
        if not user:
            logger.warning(f"Login failed: user not found: {username}")
            return None

        # Verify password
        if not self.verify_password(password, user.password_hash):
            logger.warning(f"Login failed: invalid password for user: {username}")
            return None

        # Create session
        token = secrets.token_urlsafe(32)
        session = SessionModel(
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + self.session_timeout,
        )
        db.add(session)
        db.commit()

        logger.info(f"Login successful for user: {username}")
        return user, token

    def verify_token(self, db: Session, token: str) -> Optional[User]:
        """Verify a session token and return the associated user."""
        session = db.query(SessionModel).filter(
            SessionModel.token == token,
            SessionModel.expires_at > datetime.utcnow(),
        ).first()

        if not session:
            return None

        return session.user

    def logout(self, db: Session, token: str) -> bool:
        """Invalidate a session token."""
        session = db.query(SessionModel).filter(SessionModel.token == token).first()
        if session:
            db.delete(session)
            db.commit()
            logger.info("User logged out")
            return True
        return False

    def change_password(self, db: Session, user_id: int, old_password: str, new_password: str) -> bool:
        """Change user password."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        if not self.verify_password(old_password, user.password_hash):
            logger.warning(f"Password change failed for user {user_id}: invalid old password")
            return False

        user.password_hash = self.hash_password(new_password)
        db.commit()
        logger.info(f"Password changed for user {user_id}")
        return True

    def init_admin_user(self, db: Session) -> bool:
        """Initialize admin user from environment variables."""
        username = self.settings.admin_username
        password = self.settings.admin_password

        # Check if user already exists
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            logger.info(f"Admin user already exists: {username}")
            return True

        if not password:
            logger.error("ADMIN_PASSWORD environment variable is not set")
            return False

        # Create admin user
        admin = User(
            username=username,
            password_hash=self.hash_password(password),
            is_admin=True,
        )
        db.add(admin)
        db.commit()
        logger.info(f"Admin user created: {username}")
        return True

    def cleanup_expired_sessions(self, db: Session) -> int:
        """Delete expired sessions."""
        result = db.query(SessionModel).filter(
            SessionModel.expires_at <= datetime.utcnow()
        ).delete()
        db.commit()
        logger.info(f"Cleaned up {result} expired sessions")
        return result
