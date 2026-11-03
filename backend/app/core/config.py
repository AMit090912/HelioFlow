from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import ValidationInfo, field_validator, model_validator
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

    @field_validator("demo_logins", mode="before")
    @classmethod
    def _blank_means_off(cls, value: object) -> object:
        # `.env.example` ships `DEMO_LOGINS=` blank: that means off, not a parse error at startup.
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("database_url", "test_database_url", mode="before")
    @classmethod
    def _psycopg_driver(cls, value: object) -> object:
        # Neon/Render hand out postgresql:// (or postgres://) URLs; SQLAlchemy would then look for
        # psycopg2, which is not installed. Use psycopg 3 for any plain Postgres URL.
        if isinstance(value, str):
            # Dashboards copy it as DATABASE_URL="…": tolerate pasted quotes and stray whitespace.
            value = value.strip().strip("\"'").strip()
            for prefix in ("postgresql://", "postgres://"):
                if value.startswith(prefix):
                    return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @model_validator(mode="after")
    def _production_secret(self) -> "Settings":
        # HS256 wants at least 32 bytes of key (RFC 7518 §3.2). Fail at startup, not at sign-in.
        if self.env == "production" and len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
