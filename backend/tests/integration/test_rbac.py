"""Role checks (§4 permission matrix) and the upload-size probe (Q-9)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Setting, User
from app.models.enums import UserRole

CSRF = {"X-HF-CSRF": "1"}
PASSWORD = "sunrise-roof-42"


def sign_in_as(client: TestClient, db: Session, role: UserRole) -> None:
    email = f"{role.value}@example.com"
    db.add(
        User(
            role=role,
            full_name=f"{role.value} user",
            email=email,
            password_hash=hash_password(PASSWORD),
        )
    )
    db.flush()
    res = client.post(
        "/api/auth/login", json={"identifier": email, "password": PASSWORD}, headers=CSRF
    )
    assert res.status_code == 200


@pytest.fixture
def with_setting(db_session: Session):
    db_session.add(Setting(key="generation_kwh_per_kw_year", value=1400))
    db_session.flush()


def test_anonymous_gets_401(client: TestClient):
    assert client.get("/api/rules/settings").status_code == 401


def test_homeowner_forbidden_from_staff_endpoint(client: TestClient, db_session: Session):
    sign_in_as(client, db_session, UserRole.homeowner)
    res = client.get("/api/rules/settings")
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize("role", [UserRole.sales, UserRole.admin])
def test_staff_can_read_settings(client: TestClient, db_session: Session, with_setting, role):
    sign_in_as(client, db_session, role)
    res = client.get("/api/rules/settings")
    assert res.status_code == 200
    assert {"key": "generation_kwh_per_kw_year", "value": 1400} in res.json()


def test_upload_probe_counts_bytes(client: TestClient, db_session: Session):
    sign_in_as(client, db_session, UserRole.homeowner)
    payload = b"\0" * (9 * 1024 * 1024)
    res = client.post("/api/dev/upload-probe", files={"file": ("probe.bin", payload)}, headers=CSRF)
    assert res.status_code == 200
    assert res.json() == {"received_bytes": 9 * 1024 * 1024}
