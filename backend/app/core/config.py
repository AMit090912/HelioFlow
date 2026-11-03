from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import ValidationInfo, field_validator
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
    # One-click demo sign-in on the sign-in page. Off unless DEMO_LOGINS=true (e.g. on a deployed
    # demo, so reviewers can try every role without sign-up).
    demo_logins: bool | None = None

    # AI providers (ARCHITECTURE §6). Keys stay server-side. Model defaults were verified against
    # the live accounts on 2026-11-03; override in env when a provider retires a model.
    groq_api_key: str = ""
    groq_vision_model: str = "qwen/qwen3.8-27b"
    groq_text_model: str = "openai/gpt-oss-120b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    ai_timeout_seconds: float = 20.0

    @field_validator("groq_vision_model", "groq_text_model", "gemini_model", mode="before")
    @classmethod
    def _blank_means_default(cls, value: object, info: ValidationInfo) -> object:
        # `GEMINI_MODEL=` left blank in .env means "use the default", not "an empty model name".
        if isinstance(value, str) and not value.strip():
            return cls.model_fields[info.field_name].default
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
