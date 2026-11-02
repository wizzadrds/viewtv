from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "VIEWTV API"
    environment: str = "development"
    database_url: str = "sqlite:////data/viewtv.db"
    data_dir: Path = Path("/data")
    cache_dir: Path = Path("/cache")
    cache_quota_gb: int = 80
    timezone: str = "Europe/Madrid"
    jwt_secret: str = ""
    jwt_expire_minutes: int = 720
    auth_cookie_name: str = "viewtv_session"
    auth_cookie_secure: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
