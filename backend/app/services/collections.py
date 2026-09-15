import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.models import Collection, Movie, MovieState, Exclusion, SyncRun, AuditLog
from app.schemas import CollectionCreate, CollectionUpdate, CollectionDetailResponse, MovieWithStateResponse, MovieStateResponse
from app.services.tmdb import TMDbClient
from app.services.radarr import RadarrClient
from app.services.filesystem import FilesystemAnalyzer
from app.services.matching import MovieMatcher
from app.config import get_settings

logger = logging.getLogger(__name__)


class CollectionService:
    """Manage movie collections from TMDb."""

    def __init__(self):
        self.settings = get_settings()
        self.tmdb = TMDbClient()
        self.radarr = RadarrClient()
        self.filesystem = FilesystemAnalyzer()
        self.matcher = MovieMatcher()

    async def create_collection(self, db: Session, collection_data: CollectionCreate) -> Collection:
        """Create a new collection."""
        logger.info(f"Creating collection: {collection_data.name}")

        # Check if collection already exists
        existing = db.query(Collection).filter(
            Collection.tmdb_collection_id == collection_data.tmdb_collection_id
        ).first()
        if existing:
            logger.warning(f"Collection already exists: {collection_data.name}")
            return existing

        # Create collection
        collection = Collection(**collection_data.model_dump())
        db.add(collection)
        db.commit()
        db.refresh(collection)

        # Log action
        self._audit_log(
            db,
            action="COLLECTION_ADDED",
            collection_id=collection.id,
            details={"name": collection.name, "tmdb_id": collection.tmdb_collection_id},
            result="success",
        )

        logger.info(f"Collection created: {collection.name} (ID: {collection.id})")
        return collection

    async def get_collection(self, db: Session, collection_id: int) -> Optional[Collection]:
        """Get a collection by ID."""
        return db.query(Collection).filter(Collection.id == collection_id).first()

    async def get_collections(self, db: Session, enabled_only: bool = False) -> List[Collection]:
        """Get all collections."""
        query = db.query(Collection)
        if enabled_only:
            query = query.filter(Collection.enabled == True)
        return query.all()

    async def update_collection(self, db: Session, collection_id: int, update_data: CollectionUpdate) -> Optional[Collection]:
        """Update a collection."""
        collection = await self.get_collection(db, collection_id)
        if not collection:
            return None

        logger.info(f"Updating collection: {collection.name}")

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(collection, key, value)

        db.commit()
        db.refresh(collection)

        self._audit_log(
            db,
            action="COLLECTION_UPDATED",
            collection_id=collection.id,
            details=update_dict,
            result="success",
        )

        return collection

    async def delete_collection(self, db: Session, collection_id: int) -> bool:
        """Delete a collection."""
        collection = await self.get_collection(db, collection_id)
        if not collection:
            return False

        logger.info(f"Deleting collection: {collection.name}")
        name = collection.name
        db.delete(collection)
        db.commit()

        self._audit_log(
            db,
            action="COLLECTION_REMOVED",
            collection_id=collection_id,
            details={"name": name},
            result="success",
        )

        return True

    async def sync_collection(self, db: Session, collection_id: int) -> Dict[str, Any]:
        """Synchronize a collection with TMDb.
        
        Returns sync statistics.
        """
        collection = await self.get_collection(db, collection_id)
        if not collection:
            raise ValueError(f"Collection {collection_id} not found")

        logger.info(f"Starting sync for collection: {collection.name}")

        sync_run = SyncRun(
            collection_id=collection.id,
            status="running",
        )
        db.add(sync_run)
        db.commit()

        try:
            # Fetch TMDb collection
            tmdb_collection = await self.tmdb.get_collection(collection.tmdb_collection_id)
            tmdb_movies = tmdb_collection.get("parts", [])
            logger.info(f"Found {len(tmdb_movies)} movies in TMDb collection")

            # Get Radarr movies
            radarr_movies = await self.radarr.get_movies()

            # Get filesystem movies
            fs_movies = self.filesystem.scan_library()

            # Get exclusions
            exclusions = db.query(Exclusion).filter(
                Exclusion.collection_id == collection.id
            ).all()
            excluded_tmdb_ids = {e.tmdb_movie_id for e in exclusions}

            # Process each movie
            added_count = 0
            skipped_count = 0
            failed_count = 0

            for tmdb_movie in tmdb_movies:
                tmdb_id = tmdb_movie.get("id")

                # Check if already in database
                existing_movie = db.query(Movie).filter(
                    Movie.collection_id == collection.id,
                    Movie.tmdb_movie_id == tmdb_id,
                ).first()

                if not existing_movie:
                    # Create movie record
                    movie = Movie(
                        collection_id=collection.id,
                        tmdb_movie_id=tmdb_id,
                        title=tmdb_movie.get("title", ""),
                        release_date=tmdb_movie.get("release_date"),
                        year=int(tmdb_movie.get("release_date", "").split("-")[0]) if tmdb_movie.get("release_date") else None,
                        imdb_id=tmdb_movie.get("external_ids", {}).get("imdb_id") if isinstance(tmdb_movie.get("external_ids"), dict) else None,
                        poster_path=tmdb_movie.get("poster_path"),
                        backdrop_path=tmdb_movie.get("backdrop_path"),
                        overview=tmdb_movie.get("overview"),
                    )
                    db.add(movie)
                    db.commit()
                    db.refresh(movie)
                else:
                    movie = existing_movie

                # Determine movie state
                await self._analyze_movie_state(db, movie, radarr_movies, fs_movies, excluded_tmdb_ids)
                state = db.query(MovieState).filter(MovieState.movie_id == movie.id).first()

                # Automatic acquisition is opt-in and only applies to genuinely
                # missing movies. Existing filesystem files and exclusions are
                # never sent to Radarr.
                if (
                    state
                    and state.status == "missing"
                    and (collection.auto_add_missing or self.settings.auto_add_missing)
                ):
                    try:
                        added = await self.radarr.add_movie(
                            {
                                "tmdbId": movie.tmdb_movie_id,
                                "title": movie.title,
                                "year": movie.year,
                                "qualityProfileId": (
                                    collection.quality_profile_id
                                    or self.settings.radarr_quality_profile_id
                                ),
                                "rootFolderPath": (
                                    collection.root_folder_path
                                    or self.settings.radarr_root_folder
                                ),
                                "monitored": True,
                                "addOptions": {"searchForMovie": True},
                            }
                        )
                        if added.get("error") == "duplicate":
                            skipped_count += 1
                        else:
                            added_count += 1
                            radarr_movies.append(added)
                            state.status = "managed"
                            state.radarr_managed = True
                            state.radarr_movie_id = added.get("id")
                            db.commit()
                        self._audit_log(
                            db,
                            action="MOVIE_ADDED_TO_RADARR",
                            collection_id=collection.id,
                            tmdb_movie_id=movie.tmdb_movie_id,
                            radarr_movie_id=added.get("id"),
                            details={"automatic": True},
                            result="success",
                        )
                    except Exception as exc:
                        failed_count += 1
                        self._audit_log(
                            db,
                            action="MOVIE_ADDED_TO_RADARR",
                            collection_id=collection.id,
                            tmdb_movie_id=movie.tmdb_movie_id,
                            details={"automatic": True},
                            result="failed",
                            error_message=str(exc),
                        )

            sync_run.status = "completed"
            sync_run.completed_at = datetime.utcnow()
            sync_run.movies_discovered = len(tmdb_movies)
            collection.last_sync_at = datetime.utcnow()
            collection.next_sync_at = datetime.utcnow() + timedelta(hours=collection.sync_interval)
            db.commit()

            logger.info(f"Sync completed for {collection.name}")
            return {
                "status": "success",
                "movies_discovered": len(tmdb_movies),
                "added": added_count,
                "skipped": skipped_count,
                "failed": failed_count,
            }
        except Exception as e:
            logger.error(f"Sync failed for collection {collection.name}: {e}")
            sync_run.status = "failed"
            sync_run.error = str(e)
            sync_run.completed_at = datetime.utcnow()
            db.commit()
            raise

    async def _analyze_movie_state(
        self,
        db: Session,
        movie: Movie,
        radarr_movies: List[Dict[str, Any]],
        fs_movies: List[Dict[str, Any]],
        excluded_tmdb_ids: set,
    ) -> None:
        """Analyze and set movie state (managed, existing, missing, excluded, needs_review)."""
        # Check if excluded
        radarr_movie = None
        fs_movie = None
        if movie.tmdb_movie_id in excluded_tmdb_ids:
            status = "excluded"
            confidence = 100
        else:
            # Try to match to Radarr
            movie_data = {
                "id": movie.tmdb_movie_id,
                "title": movie.title,
                "release_date": movie.release_date,
                "imdb_id": movie.imdb_id,
            }
            radarr_match = self.matcher.match_tmdb_to_radarr(movie_data, radarr_movies)
            if radarr_match:
                radarr_movie, confidence = radarr_match
                status = "managed"
            else:
                # Try to match to filesystem
                fs_match = self.matcher.match_tmdb_to_filesystem(movie_data, fs_movies)
                if fs_match:
                    fs_movie, confidence = fs_match
                    status = "existing"
                else:
                    status = "missing"
                    confidence = 0
                    radarr_movie = None
                    fs_movie = None

        # Create or update movie state
        state = db.query(MovieState).filter(MovieState.movie_id == movie.id).first()
        if not state:
            state = MovieState(movie_id=movie.id)
            db.add(state)

        state.status = status
        state.match_confidence = confidence
        state.radarr_managed = bool(radarr_movie)
        state.radarr_movie_id = radarr_movie.get("id") if radarr_movie else None
        state.filesystem_exists = bool(fs_movie)
        state.filesystem_path = fs_movie.get("path") if fs_movie else None
        state.last_checked_at = datetime.utcnow()
        db.commit()

    async def exclude_movie(self, db: Session, collection_id: int, tmdb_movie_id: int, reason: str = None) -> bool:
        """Exclude a movie from automatic acquisition."""
        logger.info(f"Excluding movie {tmdb_movie_id} from collection {collection_id}")

        # Check if already excluded
        existing = db.query(Exclusion).filter(
            Exclusion.collection_id == collection_id,
            Exclusion.tmdb_movie_id == tmdb_movie_id,
        ).first()
        if existing:
            return True

        exclusion = Exclusion(
            collection_id=collection_id,
            tmdb_movie_id=tmdb_movie_id,
            reason=reason,
        )
        db.add(exclusion)
        db.commit()

        self._audit_log(
            db,
            action="MOVIE_EXCLUDED",
            collection_id=collection_id,
            tmdb_movie_id=tmdb_movie_id,
            details={"reason": reason},
            result="success",
        )

        return True

    async def unexclude_movie(self, db: Session, collection_id: int, tmdb_movie_id: int) -> bool:
        """Remove exclusion from a movie."""
        logger.info(f"Un-excluding movie {tmdb_movie_id} from collection {collection_id}")

        exclusion = db.query(Exclusion).filter(
            Exclusion.collection_id == collection_id,
            Exclusion.tmdb_movie_id == tmdb_movie_id,
        ).first()
        if not exclusion:
            return False

        db.delete(exclusion)
        db.commit()

        self._audit_log(
            db,
            action="MOVIE_UNEXCLUDED",
            collection_id=collection_id,
            tmdb_movie_id=tmdb_movie_id,
            result="success",
        )

        return True

    def _audit_log(
        self,
        db: Session,
        action: str,
        collection_id: int = None,
        tmdb_movie_id: int = None,
        radarr_movie_id: int = None,
        details: Dict[str, Any] = None,
        result: str = "success",
        error_message: str = None,
    ) -> None:
        """Create an audit log entry."""
        log = AuditLog(
            timestamp=datetime.utcnow(),
            action=action,
            collection_id=collection_id,
            tmdb_movie_id=tmdb_movie_id,
            radarr_movie_id=radarr_movie_id,
            details=details,
            result=result,
            error_message=error_message,
        )
        db.add(log)
        db.commit()
