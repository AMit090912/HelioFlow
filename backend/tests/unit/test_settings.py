"""Production refuses weak configuration at startup instead of failing on first sign-in."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_needs_a_long_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, env="production", jwt_secret="short")
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, env="production", jwt_secret="")
    ok = Settings(_env_file=None, env="production", jwt_secret="x" * 32)
    assert len(ok.jwt_secret) == 32


def test_development_allows_a_short_secret():
    assert Settings(_env_file=None, env="development", jwt_secret="dev").jwt_secret == "dev"


@pytest.mark.parametrize(
    "given",
    [
        "postgresql://u:p@ep-x.neon.tech/helio?sslmode=require",
        "postgres://u:p@ep-x.neon.tech/helio?sslmode=require",
        "postgresql+psycopg://u:p@ep-x.neon.tech/helio?sslmode=require",
    ],
)
def test_a_pasted_neon_url_uses_the_installed_driver(given):
    """Neon hands out postgresql:// URLs; SQLAlchemy would pick psycopg2 (not installed)."""
    url = Settings(_env_file=None, database_url=given).database_url
    assert url == "postgresql+psycopg://u:p@ep-x.neon.tech/helio?sslmode=require"


def test_blank_demo_logins_means_off(monkeypatch):
    """`.env.example` ships `DEMO_LOGINS=` blank; that must not stop the API from starting."""
    monkeypatch.setenv("DEMO_LOGINS", "")
    assert Settings(_env_file=None).demo_logins is None
    monkeypatch.setenv("DEMO_LOGINS", "true")
    assert Settings(_env_file=None).demo_logins is True
