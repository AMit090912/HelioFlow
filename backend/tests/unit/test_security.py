from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.security import (
    create_session_token,
    decode_session_token,
    hash_password,
    is_common_password,
    normalize_email,
    normalize_phone,
    verify_password,
)


def test_hash_round_trip():
    hashed = hash_password("sunrise-roof-42")
    assert hashed != "sunrise-roof-42"
    assert verify_password("sunrise-roof-42", hashed)
    assert not verify_password("wrong-password", hashed)


def test_common_password_detected():
    assert is_common_password("password123")
    assert is_common_password("PASSWORD123")
    assert not is_common_password("sunrise-roof-42")


def test_token_round_trip():
    user_id = uuid4()
    claims = decode_session_token(create_session_token(user_id, "sales"))
    assert claims is not None
    assert claims.user_id == user_id
    assert claims.role == "sales"


def test_token_expired_returns_none():
    token = create_session_token(uuid4(), "homeowner", now=datetime.now(UTC) - timedelta(hours=9))
    assert decode_session_token(token) is None


def test_token_tampered_returns_none():
    token = create_session_token(uuid4(), "homeowner")
    head, payload, sig = token.split(".")
    tampered = f"{head}.{payload}.{sig[:-2]}{'AA' if sig[-2:] != 'AA' else 'BB'}"
    assert decode_session_token(tampered) is None
    assert decode_session_token("garbage") is None
    assert decode_session_token("") is None


def test_normalize_phone_indian_formats():
    for raw in ["+91 98765 43210", "098765-43210", "9876543210", "91 9876543210", "(987) 654-3210"]:
        assert normalize_phone(raw) == "9876543210", raw
    assert normalize_phone("12345") is None
    assert normalize_phone("5876543210") is None
    assert normalize_phone("abc") is None


def test_normalize_email():
    assert normalize_email(" Prashant@Example.com ") == "prashant@example.com"
