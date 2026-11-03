"""Rules and settings editing (§2 screen 9, §3.5–3.7, §9.3): admin writes, sales reads."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models import Setting, User
from app.models.enums import UserRole
from seed import run as seed
from tests.integration.test_bills_api import CSRF, PASSWORD, make_staff, sign_in

TODAY = date.today()


@pytest.fixture
def admin(client, db_session):
    seed(db_session, "seed-pass-for-tests")
    db_session.add(
        User(
            role=UserRole.admin,
            full_name="Admin",
            email="boss@example.com",
            password_hash=hash_password(PASSWORD),
        )
    )
    db_session.flush()
    sign_in(client, "boss@example.com")
    return client


def price_body(**overrides):
    return {
        "min_kw": "1",
        "max_kw": "10",
        "price_per_kw": "65000",
        "gst_inclusive": True,
        "effective_from": str(TODAY + timedelta(days=30)),
        "note": "test",
        **overrides,
    }


def test_sales_can_view_admin_can_edit(admin, db_session):
    make_staff(db_session, "viewer@example.com")
    sign_in(admin, "viewer@example.com")
    assert admin.get("/api/rules/price").status_code == 200
    assert admin.get("/api/rules/subsidy").status_code == 200
    assert admin.get("/api/rules/settings").status_code == 200
    assert admin.post("/api/rules/price", headers=CSRF, json=price_body()).status_code == 403
    put = admin.put("/api/rules/settings/roof_sqft_per_kw", headers=CSRF, json={"value": 90})
    assert put.status_code == 403


def test_price_rules_listed_with_plain_numbers(admin):
    [rule] = admin.get("/api/rules/price").json()
    assert rule["price_per_kw"] == "60000" and rule["effective_to"] is None
    assert rule["min_kw"] == "1" and rule["gst_inclusive"] is True


def test_overlapping_price_rule_is_409(admin):
    res = admin.post("/api/rules/price", headers=CSRF, json=price_body())  # seed rule is open-ended
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "RULE_OVERLAP"


def test_rule_change_applies_from_its_date(admin):
    [old] = admin.get("/api/rules/price").json()
    closed = admin.patch(
        f"/api/rules/price/{old['id']}",
        headers=CSRF,
        json={"effective_to": str(TODAY - timedelta(days=1))},
    )
    assert closed.status_code == 200 and closed.json()["effective_to"] == str(TODAY - timedelta(1))
    new = admin.post("/api/rules/price", headers=CSRF, json=price_body(effective_from=str(TODAY)))
    assert new.status_code == 201, new.text
    assert [r["price_per_kw"] for r in admin.get("/api/rules/price").json()] == ["60000", "65000"]


def test_closing_rule_into_overlap_is_409(admin):
    [old] = admin.get("/api/rules/price").json()
    admin.patch(
        f"/api/rules/price/{old['id']}",
        headers=CSRF,
        json={"effective_to": str(TODAY + timedelta(days=9))},
    )
    later = admin.post(
        "/api/rules/price", headers=CSRF, json=price_body(effective_from=str(TODAY + timedelta(10)))
    )
    assert later.status_code == 201
    # Re-opening the old rule past the new one's start would overlap.
    reopen = admin.patch(
        f"/api/rules/price/{old['id']}",
        headers=CSRF,
        json={"effective_to": str(TODAY + timedelta(days=20))},
    )
    assert (reopen.status_code, reopen.json()["error"]["code"]) == (409, "RULE_OVERLAP")
    before_start = admin.patch(
        f"/api/rules/price/{old['id']}",
        headers=CSRF,
        json={"effective_to": "2025-12-31"},  # before effective_from 2026-01-01
    )
    assert (before_start.status_code, before_start.json()["error"]["code"]) == (
        422,
        "RULE_INVALID",
    )


def test_price_rule_validation(admin):
    bad = admin.post("/api/rules/price", headers=CSRF, json=price_body(min_kw="5", max_kw="2"))
    assert bad.status_code == 422
    exclusive = admin.post("/api/rules/price", headers=CSRF, json=price_body(gst_inclusive=False))
    assert (exclusive.status_code, exclusive.json()["error"]["code"]) == (422, "GST_EXCLUSIVE")


def test_subsidy_slabs_validated(admin):
    [old] = admin.get("/api/rules/subsidy").json()
    assert old["slabs"][0] == {"from_kw": "0", "to_kw": "2", "amount_per_kw": "30000"}
    admin.patch(
        f"/api/rules/subsidy/{old['id']}",
        headers=CSRF,
        json={"effective_to": str(TODAY + timedelta(days=29))},
    )
    body = {
        "scheme_code": "CENTRAL_RESIDENTIAL",
        "segment": "residential",
        "cap_amount": "78000",
        "effective_from": str(TODAY + timedelta(days=30)),
        "source_note": "Test rule",
    }
    gap = [
        {"from_kw": "0", "to_kw": "2", "amount_per_kw": "30000"},
        {"from_kw": "3", "to_kw": "4", "amount_per_kw": "1000"},
    ]
    res = admin.post("/api/rules/subsidy", headers=CSRF, json={**body, "slabs": gap})
    assert res.status_code == 422
    ok_slabs = [{"from_kw": "0", "to_kw": "3", "amount_per_kw": "25000"}]
    ok = admin.post("/api/rules/subsidy", headers=CSRF, json={**body, "slabs": ok_slabs})
    assert ok.status_code == 201, ok.text


def test_setting_validated(admin, db_session):
    bad = admin.put(
        "/api/rules/settings/usable_generation_pct", headers=CSRF, json={"value": "1.5"}
    )
    assert (bad.status_code, bad.json()["error"]["code"]) == (422, "SETTING_INVALID")
    offsets = admin.put(
        "/api/rules/settings/quote_option_offsets", headers=CSRF, json={"value": [1, 2]}
    )
    assert offsets.status_code == 422  # must include 0
    ok = admin.put(
        "/api/rules/settings/usable_generation_pct", headers=CSRF, json={"value": "0.85"}
    )
    assert ok.status_code == 200 and ok.json()["value"] == "0.85"
    row = db_session.execute(
        select(Setting).where(Setting.key == "usable_generation_pct")
    ).scalar_one()
    assert row.value == "0.85" and row.updated_by is not None


def test_unknown_setting_404(admin):
    res = admin.put("/api/rules/settings/free_money", headers=CSRF, json={"value": 1})
    assert res.status_code == 404


def test_overlap_message_names_the_conflicting_rule(admin):
    res = admin.post(
        "/api/rules/price",
        headers=CSRF,
        json=price_body(min_kw="10", max_kw="12", effective_from=str(TODAY)),
    )
    body = res.json()["error"]
    assert res.status_code == 409 and body["code"] == "RULE_OVERLAP"
    assert "1–10 kW" in body["message"] and "2026-01-01" in body["message"]
    assert body["details"][0]["effective_from"] == "2026-01-01"
