"""Review finding 2: limiter memory must not grow on lookups; client IP from trusted proxy."""

from types import SimpleNamespace

from app.core.config import get_settings
from app.core.ratelimit import SlidingWindowLimiter, client_ip


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_lookup_does_not_create_entries():
    limiter = SlidingWindowLimiter(limit=5, window_seconds=60)
    for i in range(1000):
        assert not limiter.is_blocked(f"ip|user{i}@example.com")
    assert limiter.size() == 0


def test_expired_entries_are_removed():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60, clock=clock)
    limiter.record("k")
    limiter.record("k")
    assert limiter.is_blocked("k")
    clock.now = 61
    assert not limiter.is_blocked("k")
    assert limiter.size() == 0


def _request(host: str, xff: str | None = None):
    headers = {"x-forwarded-for": xff} if xff else {}
    return SimpleNamespace(client=SimpleNamespace(host=host), headers=headers)


def test_client_ip_ignores_forwarded_header_unless_trusted(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "false")
    get_settings.cache_clear()
    assert client_ip(_request("10.0.0.1", "203.0.113.9")) == "10.0.0.1"


def test_client_ip_uses_first_forwarded_hop_when_trusted(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    get_settings.cache_clear()
    try:
        assert client_ip(_request("10.0.0.1", "203.0.113.9, 10.0.0.1")) == "203.0.113.9"
        assert client_ip(_request("10.0.0.1")) == "10.0.0.1"
    finally:
        monkeypatch.delenv("TRUST_PROXY_HEADERS")
        get_settings.cache_clear()
