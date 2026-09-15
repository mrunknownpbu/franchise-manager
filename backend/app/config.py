from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_port: int = 8787
    database_path: str = './data/franchise-manager.db'
    tmdb_api_key: str = ''
    tmdb_request_timeout: float = 15
    tmdb_max_retries: int = 3
    radarr_url: str = ''
    radarr_api_key: str = ''
    radarr_root_folder: str = '/movies'
    radarr_quality_profile_id: int = 1
    radarr_request_timeout: float = 15
    radarr_max_retries: int = 3
    movie_library_path: str = '/movies'
    admin_username: str = 'admin'
    admin_password: str = ''
    sync_enabled: bool = True
    sync_interval_hours: int = 6
    auto_add_missing: bool = False
    match_confidence_threshold: float = 70
    session_timeout_hours: int = 24
    session_secret_key: str = 'change-me-in-production'
    log_level: str = 'INFO'
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')
    @property
    def database_url(self):
        path = Path(self.database_path)
        if path.parent != Path('.'):
            path.parent.mkdir(parents=True, exist_ok=True)
        return f'sqlite:///{path.as_posix()}'

@lru_cache
def get_settings(): return Settings()
