from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "VIEWTV API"
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("VIEWTV_ENV", "ENVIRONMENT"),
    )
    database_url: str = "sqlite:////data/viewtv.db"
    data_dir: Path = Path("/data")
    cache_dir: Path = Path("/cache")
    cache_quota_gb: int = 80
    timezone: str = Field(
        default="Europe/Madrid",
        validation_alias=AliasChoices("VIEWTV_TIMEZONE", "TIMEZONE"),
    )
    jwt_secret: str = ""
    jwt_expire_minutes: int = Field(default=720, gt=0, le=10080)
    auth_cookie_name: str = "viewtv_session"
    auth_cookie_secure: bool = False
    jellyfin_base_url: str = ""
    jellyfin_api_key: str = ""
    jellyfin_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    tmdb_api_key: str = ""
    tmdb_language: str = "es-ES"
    tmdb_timeout_seconds: float = Field(default=5.0, gt=0, le=60)

    jackett_base_url: str = ""
    jackett_api_key: str = ""
    jackett_timeout_seconds: float = Field(default=20.0, gt=0, le=120)

    qbittorrent_base_url: str = ""
    qbittorrent_api_key: str = ""
    qbittorrent_timeout_seconds: float = Field(default=10.0, gt=0, le=120)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
