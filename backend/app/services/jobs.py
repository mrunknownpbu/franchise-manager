import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.models import Job
from app.config import get_settings

logger = logging.getLogger(__name__)


class JobService:
    """Manage background jobs."""

    def __init__(self):
        self.settings = get_settings()

    def create_job(self, db: Session, job_id: str, name: str, total_steps: int = 0) -> Job:
        """Create a new job."""
        logger.info(f"Creating job: {name} (ID: {job_id})")
        
        job = Job(
            job_id=job_id,
            name=name,
            status="queued",
            total_steps=total_steps,
            started_at=datetime.utcnow(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def get_job(self, db: Session, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return db.query(Job).filter(Job.job_id == job_id).first()

    def update_job_progress(self, db: Session, job_id: str, current_step: int, progress: int = None) -> Optional[Job]:
        """Update job progress."""
        job = self.get_job(db, job_id)
        if not job:
            return None

        job.current_step = current_step
        if progress is not None:
            job.progress = progress
        else:
            job.progress = int((current_step / max(job.total_steps, 1)) * 100)
        
        db.commit()
        db.refresh(job)
        return job

    def complete_job(self, db: Session, job_id: str, result: Dict[str, Any] = None) -> Optional[Job]:
        """Mark job as completed."""
        job = self.get_job(db, job_id)
        if not job:
            return None

        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.utcnow()
        job.result = result
        db.commit()
        db.refresh(job)
        logger.info(f"Job completed: {job.name}")
        return job

    def fail_job(self, db: Session, job_id: str, error: str) -> Optional[Job]:
        """Mark job as failed."""
        job = self.get_job(db, job_id)
        if not job:
            return None

        job.status = "failed"
        job.error = error
        job.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        logger.error(f"Job failed: {job.name} - {error}")
        return job

    def get_active_jobs(self, db: Session) -> List[Job]:
        """Get all active jobs."""
        return db.query(Job).filter(Job.status.in_(["queued", "running"])).all()

    def get_recent_jobs(self, db: Session, limit: int = 20) -> List[Job]:
        """Get recent jobs."""
        return db.query(Job).order_by(Job.started_at.desc()).limit(limit).all()
