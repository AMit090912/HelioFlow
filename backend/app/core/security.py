"""Password hashing, session tokens and login identifier normalisation (§4)."""

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

_hasher = PasswordHash.recommended()  # argon2id
_ALGORITHM = "HS256"
_PHONE_RE = re.compile(r"^[6-9]\d{9}$")
_COMMON_PASSWORDS_FILE = Path(__file__).with_name("common_passwords.txt")


@dataclass(frozen=True)
class SessionClaims:
    user_id: uuid.UUID
    role: str


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(plain, hashed)
    except Exception:  # malformed hash in the database must never crash login
        return False


@lru_cache
def _common_passwords() -> frozenset[str]:
    lines = _COMMON_PASSWORDS_FILE.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip().lower() for line in lines if line.strip())


def is_common_password(plain: str) -> bool:
    return plain.strip().lower() in _common_passwords()


def _secret() -> str:
    secret = get_settings().jwt_secret
    if not secret:
        raise RuntimeError("JWT_SECRET is not set")
    return secret


def create_session_token(user_id: uuid.UUID, role: str, now: datetime | None = None) -> str:
    issued = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(hours=get_settings().jwt_ttl_hours)).timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def decode_session_token(token: str) -> SessionClaims | None:
    """Return the claims, or None for anything invalid. Never raises."""
    if not token:
        return None
    try:
        payload = jwt.decode(
            token, _secret(), algorithms=[_ALGORITHM], options={"require": ["sub", "exp", "role"]}
        )
        return SessionClaims(user_id=uuid.UUID(payload["sub"]), role=str(payload["role"]))
    except (jwt.PyJWTError, ValueError, KeyError):
        return None


def normalize_email(raw: str) -> str:
    return raw.strip().lower()


def normalize_phone(raw: str) -> str | None:
    """Indian mobile number as 10 digits, accepting +91 / 91 / 0 prefixes and separators."""
    digits = re.sub(r"[\s\-()+]", "", raw or "")
    if not digits.isdigit():
        return None
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if _PHONE_RE.match(digits) else None
