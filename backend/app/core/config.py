"""Validated application configuration sourced only from environment variables."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Distributed Chat Application"
    debug: bool = False
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_cors_origins: list[str] = [
        "http://localhost:3000",
        "https://frontend-nu-two-49.vercel.app",
    ]

    mongodb_uri: str = ""
    mongodb_database: str = "chat_db"
    mongodb_max_pool_size: int = 50
    mongodb_min_pool_size: int = 1
    mongodb_server_selection_timeout_ms: int = 5000
    mongodb_connect_timeout_ms: int = 5000

    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""
    upstash_redis_retries: int = 2
    upstash_redis_retry_interval: float = 0.5
    upstash_event_channel: str = "chat:events"

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    cookie_secure: bool = True
    rate_limit_messages_per_window: int = 20
    rate_limit_window_seconds: int = 10

    def validate_runtime_settings(self) -> None:
        """Fail fast on startup rather than accepting insecure placeholder settings."""
        required = {
            "MONGODB_URI": self.mongodb_uri,
            "UPSTASH_REDIS_REST_URL": self.upstash_redis_rest_url,
            "UPSTASH_REDIS_REST_TOKEN": self.upstash_redis_rest_token,
            "JWT_SECRET_KEY": self.jwt_secret_key,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Missing required environment variables: {joined}")
        if len(self.jwt_secret_key) < 32:
            raise RuntimeError("JWT_SECRET_KEY must be at least 32 characters long")
        if not self.mongodb_uri.startswith(("mongodb://", "mongodb+srv://")):
            raise RuntimeError("MONGODB_URI must be a mongodb:// or mongodb+srv:// URI")
        if not self.upstash_redis_rest_url.startswith("https://"):
            raise RuntimeError("UPSTASH_REDIS_REST_URL must use HTTPS")


settings = Settings()
