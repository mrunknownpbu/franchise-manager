from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Any


# Authentication Schemas
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: "UserResponse"


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool

    class Config:
        from_attributes = True


# Collection Schemas
class CollectionCreate(BaseModel):
    tmdb_collection_id: int
    name: str
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    overview: Optional[str] = None
    enabled: bool = True
    auto_add_missing: bool = False
    quality_profile_id: Optional[int] = None
    root_folder_path: Optional[str] = None
    sync_interval: int = 6


class CollectionUpdate(BaseModel):
    enabled: Optional[bool] = None
    auto_add_missing: Optional[bool] = None
    quality_profile_id: Optional[int] = None
    root_folder_path: Optional[str] = None
    sync_interval: Optional[int] = None


class CollectionResponse(BaseModel):
    id: int
    tmdb_collection_id: int
    name: str
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    overview: Optional[str] = None
    enabled: bool
    auto_add_missing: bool
    quality_profile_id: Optional[int] = None
    root_folder_path: Optional[str] = None
    sync_interval: int
    last_sync_at: Optional[datetime] = None
    next_sync_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Movie Schemas
class MovieResponse(BaseModel):
    id: int
    collection_id: int
    tmdb_movie_id: int
    title: str
    release_date: Optional[str] = None
    year: Optional[int] = None
    imdb_id: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    overview: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Movie State Schemas
class MovieStateResponse(BaseModel):
    id: int
    movie_id: int
    radarr_movie_id: Optional[int] = None
    radarr_managed: bool
    filesystem_exists: bool
    filesystem_path: Optional[str] = None
    status: str
    match_confidence: float
    last_checked_at: datetime

    class Config:
        from_attributes = True


class MovieWithStateResponse(MovieResponse):
    state: Optional[MovieStateResponse] = None


# Exclusion Schemas
class ExclusionCreate(BaseModel):
    reason: Optional[str] = None


class ExclusionResponse(BaseModel):
    id: int
    collection_id: int
    tmdb_movie_id: int
    reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Sync Schemas
class SyncRunResponse(BaseModel):
    id: int
    collection_id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    movies_discovered: int
    movies_added: int
    movies_skipped: int
    movies_failed: int
    error: Optional[str] = None

    class Config:
        from_attributes = True


# Audit Log Schemas
class AuditLogResponse(BaseModel):
    id: int
    timestamp: datetime
    action: str
    collection_id: Optional[int] = None
    tmdb_movie_id: Optional[int] = None
    radarr_movie_id: Optional[int] = None
    details: Optional[Any] = None
    result: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


# Job Schemas
class JobResponse(BaseModel):
    id: int
    job_id: str
    name: str
    status: str
    progress: int
    total_steps: int
    current_step: int
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# TMDb Schemas
class TMDbCollectionMovie(BaseModel):
    id: int
    title: str
    release_date: Optional[str] = None
    poster_path: Optional[str] = None
    overview: Optional[str] = None


class TMDbCollectionResponse(BaseModel):
    id: int
    name: str
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    parts: List[TMDbCollectionMovie]


# Radarr Schemas
class RadarrProfile(BaseModel):
    id: int
    name: str


class RadarrRootFolder(BaseModel):
    id: int
    path: str


class RadarrStatus(BaseModel):
    version: str
    osVersion: str
    isWindows: bool
    isLinux: bool
    isOsx: bool
    isDocker: bool
    isAdmin: bool
    isUserInteractive: bool
    startupPath: str
    appData: str
    osVersion_display: str


# API Response Schemas
class HealthResponse(BaseModel):
    status: str  # healthy, degraded
    database: str  # healthy, unhealthy
    radarr: str  # healthy, unhealthy, unknown
    tmdb: str  # healthy, unhealthy, unknown
    filesystem: str  # healthy, unhealthy
    timestamp: datetime


class BulkAddMoviesRequest(BaseModel):
    movie_ids: List[int]


class BulkAddMoviesResponse(BaseModel):
    added: int
    skipped: int
    existing: int
    failed: int
    errors: List[dict]


class CollectionDetailResponse(CollectionResponse):
    movies: List[MovieWithStateResponse] = []
    movie_count: int = 0
    managed_count: int = 0
    existing_count: int = 0
    missing_count: int = 0
    excluded_count: int = 0
    needs_review_count: int = 0
