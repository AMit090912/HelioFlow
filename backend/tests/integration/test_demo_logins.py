"""One-click demo sign-in for testing and reviewers (no typing, no sign-up each time)."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from seed import run as seed

CSRF = {"X-HF-CSRF": "1"}


def demo(client: TestClient, who: str, locale: str = "en"):
    return client.post("/api/auth/demo-login", headers=CSRF, json={"as": who, "locale": locale})


@pytest.fixture
def enabled(monkeypatch, db_session):
    monkeypatch.setattr(get_settings(), "demo_logins", True)
    seed(db_session, "seed-pass-for-tests")


def test_new_homeowner_is_a_fresh_account_each_time(client, enabled):
    first = demo(client, "new_homeowner", "hi").json()
    client.cookies.clear()
    second = demo(client, "new_homeowner").json()
    assert first["id"] != second["id"]
    assert first["role"] == "homeowner" and first["preferred_locale"] == "hi"
    assert client.get("/api/auth/me").json()["id"] == second["id"]  # signed in by the cookie
    assert client.get("/api/leads/mine").json() == []  # a clean start


def test_demo_homeowner_is_the_same_account_every_time(client, enabled):
    first = demo(client, "homeowner").json()
    client.cookies.clear()
    assert demo(client, "homeowner").json()["id"] == first["id"]


@pytest.mark.parametrize("who", ["sales", "admin"])
def test_staff_demo_logins(client, enabled, who):
    user = demo(client, who).json()
    assert user["role"] == who
    assert client.get("/api/staff/leads").status_code == 200


def test_unknown_role_is_refused(client, enabled):
    assert demo(client, "superuser").status_code == 422


def test_listing_says_what_is_available(client, enabled):
    body = client.get("/api/auth/demo-logins").json()
    assert body["enabled"] is True
    assert [a["as"] for a in body["accounts"]] == ["new_homeowner", "homeowner", "sales", "admin"]


def test_switched_off_means_not_there(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_logins", False)
    assert client.get("/api/auth/demo-logins").json() == {"enabled": False, "accounts": []}
    assert demo(client, "sales").status_code == 404


def test_default_is_on_in_development_and_off_in_production(monkeypatch):
    from app.api.demo import demo_logins_enabled

    s = get_settings()
    monkeypatch.setattr(s, "demo_logins", None)
    monkeypatch.setattr(s, "env", "development")
    assert demo_logins_enabled() is True
    monkeypatch.setattr(s, "env", "production")
    assert demo_logins_enabled() is False
