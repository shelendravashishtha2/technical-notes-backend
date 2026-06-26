from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import BeforeValidator, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: str | list[str] | None) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


CSVList = Annotated[list[str], BeforeValidator(_split_csv)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Technical Notes API"
    environment: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str = Field(..., description="Async SQLAlchemy database URL")
    alembic_database_url: str | None = None
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_recycle_seconds: int = 1800

    admin_token: str = Field(..., min_length=16)
    cors_origins: CSVList = ["http://localhost:5173"]
    trusted_hosts: CSVList = ["localhost", "127.0.0.1"]

    json_response_cache_seconds: int = 60
    nav_cache_seconds: int = 300
    topic_cache_seconds: int = 900
    max_page_size: int = 100
    default_page_size: int = 30
    bootstrap_topic_limit: int = 500

    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    redis_url: str | None = None

    @computed_field  # type: ignore[misc]
    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}

    @computed_field  # type: ignore[misc]
    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @computed_field  # type: ignore[misc]
    @property
    def sync_database_url(self) -> str:
        if self.alembic_database_url:
            return self.alembic_database_url
        url = self.database_url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
