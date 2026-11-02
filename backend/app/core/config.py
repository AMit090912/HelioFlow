from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration. Values come from environment variables or backend/.env."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://helio:helio@localhost:5433/helio"
    test_database_url: str = "postgresql+psycopg://helio:helio@localhost:5433/helio_test"
    jwt_secret: str = ""
    jwt_ttl_hours: int = 8
    frontend_origin: str = "http://localhost:3000"
    cookie_secure: bool = True
    # Only enable behind a proxy that sets X-Forwarded-For (Render/Vercel); see ratelimit.client_ip.
    trust_proxy_headers: bool = False
    ai_mode: Literal["live", "demo", "test"] = "live"
    max_upload_mb: int = 10
    seed_demo_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
