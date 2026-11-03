"""Staff inbox, lead detail, verification, upgrade and close (ARCHITECTURE §2 screens 6–7, §4)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Lead
from seed import run as seed
from tests.integration.test_bills_api import CSRF, make_staff, sign_in
from tests.integration.test_leads_api import create_lead, signup

SEED_PW = "seed-pass-for-tests"


@pytest.fixture
def staff(client: TestClient, db_session: Session):
    from contextlib import nullcontext

    seed(db_session, SEED_PW)
    client.app.state.session_factory = lambda: nullcontext(db_session)
    make_staff(db_session, "desk@example.com")
    sign_in(client, "desk@example.com")
    return client


def lead_id(db: Session, code: str) -> str:
    return str(db.execute(select(Lead.id).where(Lead.code == code)).scalar_one())


# --- Inbox ---


def test_inbox_orders_high_first_then_newest(staff, db_session):
    signup(staff, "drafty@example.com")
    create_lead(staff)  # a draft: hidden from the default inbox
    sign_in(staff, "desk@example.com")
    rows = staff.get("/api/staff/leads").json()
    codes = [r["code"] for r in rows]
    assert codes[0] == "LD-30881"  # Prashant: High
    assert set(codes) == {"LD-30881", "LD-30902", "LD-30915"}
    assert [r["score"] for r in rows] == ["high", "low", "low"]
    prashant = rows[0]
    assert prashant["recommended_kw"] == "3" and prashant["recommendation_status"] == "provisional"
    assert prashant["homeowner_name"] == "Prashant Wankhede"


def test_inbox_filters_by_score_and_status(staff):
    assert [r["code"] for r in staff.get("/api/staff/leads?score=high").json()] == ["LD-30881"]
    low = staff.get("/api/staff/leads?score=low").json()
    assert {r["code"] for r in low} == {"LD-30902", "LD-30915"}
    pending = staff.get("/api/staff/leads?status=call_pending").json()
    assert {r["code"] for r in pending} == {"LD-30902", "LD-30915"}
    assert staff.get("/api/staff/leads?score=medium").status_code == 422


def test_homeowner_cannot_use_staff_api(staff, db_session):
    target = lead_id(db_session, "LD-30881")
    signup(staff, "nosy@example.com")
    assert staff.get("/api/staff/leads").status_code == 403
    assert staff.get(f"/api/staff/leads/{target}").status_code == 403
    res = staff.post(
        f"/api/staff/leads/{target}/verification",
        headers=CSRF,
        json={"roof_area_sqft": "450", "via": "survey"},
    )
    assert res.status_code == 403


def test_detail_shows_ai_and_confirmed_values_and_reasons(staff, db_session):
    detail = staff.get(f"/api/staff/leads/{lead_id(db_session, 'LD-30915')}").json()
    assert detail["homeowner"]["full_name"] == "Ayesha Siddiqui"
    assert detail["homeowner"]["phone"] == "9000000003"
    assert detail["score"] == "low"
    assert detail["score_reasons"][0]["code"] == "bill_below_threshold"
    assert detail["current_reading"]["confirmed"]["avg_monthly_units"] == "85"
    assert detail["current_reading"]["source_path"] == "manual"
    assert detail["sanctioned_load"] == {"value": None, "source": None}
    assert detail["events"] == [] and detail["quotes"] == []


def test_unknown_lead_is_404(staff):
    assert staff.get("/api/staff/leads/00000000-0000-0000-0000-000000000000").status_code == 404


# --- Verification ---


def test_verification_moves_to_surveyed_and_logs_event(staff, db_session):
    target = lead_id(db_session, "LD-30881")
    res = staff.post(
        f"/api/staff/leads/{target}/verification",
        headers=CSRF,
        json={
            "roof_area_sqft": "450",
            "via": "survey",
            "sanctioned_load_kw": "3",
            "notes": "Clear south-facing roof.",
        },
    )
    assert res.status_code == 200, res.text
    detail = res.json()
    assert detail["status"] == "surveyed"
    assert detail["verified_roof_area_sqft"] == "450" and detail["roof_verified_via"] == "survey"
    assert detail["sanctioned_load"] == {"value": "3", "source": "staff"}
    assert detail["survey_notes"] == "Clear south-facing roof."
    assert [e["kind"] for e in detail["events"]] == ["verified"]
    assert detail["events"][0]["from_status"] == "survey_pending"
    assert detail["events"][0]["to_status"] == "surveyed"


def test_verification_validates_input(staff, db_session):
    target = lead_id(db_session, "LD-30881")
    for body in (
        {"roof_area_sqft": "0", "via": "survey"},
        {"roof_area_sqft": "450", "via": "drone"},
        {"roof_area_sqft": "450", "via": "call", "sanctioned_load_kw": "150"},
    ):
        assert (
            staff.post(
                f"/api/staff/leads/{target}/verification", headers=CSRF, json=body
            ).status_code
            == 422
        )


# --- Upgrade and close ---


def test_upgrade_requires_reason_and_only_from_call_pending(staff, db_session):
    ayesha = lead_id(db_session, "LD-30915")
    empty = staff.post(f"/api/staff/leads/{ayesha}/upgrade", headers=CSRF, json={"reason": " "})
    assert (empty.status_code, empty.json()["error"]["code"]) == (422, "REASON_REQUIRED")

    ok = staff.post(
        f"/api/staff/leads/{ayesha}/upgrade",
        headers=CSRF,
        json={"reason": "Bill is low only in winter; summer bills are higher."},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "survey_pending" and ok.json()["next_action"] == "survey_visit"
    assert ok.json()["events"][0]["kind"] == "upgraded"

    prashant = lead_id(db_session, "LD-30881")  # already survey_pending
    again = staff.post(
        f"/api/staff/leads/{prashant}/upgrade", headers=CSRF, json={"reason": "No reason really"}
    )
    assert (again.status_code, again.json()["error"]["code"]) == (409, "LEAD_STATUS_CONFLICT")


def test_close_lost_with_reason_is_terminal(staff, db_session):
    rohit = lead_id(db_session, "LD-30902")
    res = staff.post(
        f"/api/staff/leads/{rohit}/close", headers=CSRF, json={"reason": "Landlord said no."}
    )
    assert res.status_code == 200 and res.json()["status"] == "closed_lost"
    after = staff.post(
        f"/api/staff/leads/{rohit}/verification",
        headers=CSRF,
        json={"roof_area_sqft": "300", "via": "call"},
    )
    assert (after.status_code, after.json()["error"]["code"]) == (409, "LEAD_STATUS_CONFLICT")
    # Closed leads leave the default inbox but can be filtered for.
    assert "LD-30902" not in [r["code"] for r in staff.get("/api/staff/leads").json()]
    closed = staff.get("/api/staff/leads?status=closed_lost").json()
    assert [r["code"] for r in closed] == ["LD-30902"]


def test_resolved_flags_are_not_shown_after_verification(staff, db_session):
    ayesha = lead_id(db_session, "LD-30915")
    before = staff.get(f"/api/staff/leads/{ayesha}").json()["flags"]
    assert {"roof_unverified", "sanctioned_load_unknown"} <= set(before)
    staff.post(
        f"/api/staff/leads/{ayesha}/verification",
        headers=CSRF,
        json={"roof_area_sqft": "200", "via": "call", "sanctioned_load_kw": "2"},
    )
    after = staff.get(f"/api/staff/leads/{ayesha}").json()["flags"]
    assert "roof_unverified" not in after and "sanctioned_load_unknown" not in after
