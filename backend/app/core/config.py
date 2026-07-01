"""
Application configuration loaded from environment variables.

Uses pydantic-settings to provide validated, typed configuration with
sensible defaults for local development.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings populated from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    app_name: str = "Distributed Chat Application"
    debug: bool = False

    # ── Backend Server ───────────────────────────────────────────
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_cors_origins: list[str] = ["http://localhost:3000"]

    # ── PostgreSQL ───────────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "chat_db"
    postgres_user: str = "chatuser"
    postgres_password: str = "changeme_db_password"

    # ── Redis ────────────────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""

    # ── JWT / Auth ───────────────────────────────────────────────
    jwt_secret_key: str = "changeme_super_secret_jwt_key_at_least_32_chars"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # ── Rate Limiting ────────────────────────────────────────────
    rate_limit_messages_per_window: int = 20
    rate_limit_window_seconds: int = 10

    # ── Derived Properties ───────────────────────────────────────

    @property
    def database_url(self) -> str:
        """Async PostgreSQL connection string for SQLAlchemy."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Synchronous PostgreSQL connection string (for Alembic)."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Redis connection string."""
        password_part = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{password_part}{self.redis_host}:{self.redis_port}/0"


settings = Settings()
