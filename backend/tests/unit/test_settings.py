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
