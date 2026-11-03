"""Homeowner lead API and qualification on bill confirmation (ARCHITECTURE §2, §7, §8)."""

from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Lead
from seed import run as seed
from tests.integration.test_bills_api import BILLS, CSRF, make_staff, sign_in  # noqa: F401
from tests.unit.ai.test_ai import GOOD, Scripted

PASSWORD = "sunrise-roof-42"
HOME = {
    "ownership": "owner",
    "property_type": "home",
    "roof_type": "rcc_flat",
    "roof_area_sqft": "450",
    "monthly_bill": "3200",
    "pincode": "440010",
    "consent": True,
}


@pytest.fixture
def ai(client: TestClient, db_session: Session):
    from contextlib import nullcontext

    seed(db_session, "seed-pass-for-tests")  # settings, price and subsidy rules
    state = {"providers": [Scripted("groq", *[GOOD] * 5)]}
    client.app.state.session_factory = lambda: nullcontext(db_session)
    client.app.state.ai_providers = lambda sha: state["providers"]
    return state


def signup(client: TestClient, email: str) -> None:
    client.cookies.clear()
    res = client.post(
        "/api/auth/signup",
        headers=CSRF,
        json={
            "full_name": "Test Homeowner",
            "email": email,
            "password": PASSWORD,
        },
    )
    assert res.status_code == 201


def create_lead(client: TestClient, **overrides) -> dict:
    res = client.post("/api/leads", headers=CSRF, json={**HOME, **overrides})
    assert res.status_code == 201, res.text
    return res.json()


def upload_and_confirm(client: TestClient, lead_id: str, confirm: dict) -> dict:
    up = client.post(
        f"/api/leads/{lead_id}/bills",
        headers=CSRF,
        files={"file": ("bill.jpg", (BILLS / "clear.jpg").read_bytes())},
    )
    assert up.status_code == 202, up.text
    res = client.post(f"/api/bills/{up.json()['id']}/confirm", headers=CSRF, json=confirm)
    assert res.status_code == 200, res.text
    return client.get(f"/api/leads/{lead_id}").json()


# --- Create, list, privacy ---


def test_homeowner_creates_a_lead(client, ai):
    signup(client, "new@example.com")
    lead = create_lead(client)
    assert lead["code"].startswith("LD-") and len(lead["code"]) == 9
    assert lead["status"] == "draft"
    assert lead["next_action"] is None and lead["recommended_kw"] is None
    assert "score" not in lead and "score_reasons" not in lead  # §2: never shown to homeowners


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"pincode": "04001"}, "pincode"),
        ({"monthly_bill": "0"}, "monthly_bill"),
        ({"roof_area_sqft": "-5"}, "roof_area_sqft"),
        ({"ownership": "landlord"}, "ownership"),
    ],
)
def test_lead_input_is_validated(client, ai, override, field):
    signup(client, "v@example.com")
    res = client.post("/api/leads", headers=CSRF, json={**HOME, **override})
    assert res.status_code == 422
    assert field in {d["field"] for d in res.json()["error"]["details"]}


def test_consent_is_required(client, ai):
    signup(client, "c@example.com")
    res = client.post("/api/leads", headers=CSRF, json={**HOME, "consent": False})
    assert (res.status_code, res.json()["error"]["code"]) == (422, "CONSENT_REQUIRED")


def test_staff_cannot_create_homeowner_leads(client, ai, db_session):
    make_staff(db_session, "staff@example.com")
    sign_in(client, "staff@example.com")
    assert client.post("/api/leads", headers=CSRF, json=HOME).status_code == 403


def test_my_leads_lists_only_mine_newest_first(client, ai):
    signup(client, "a@example.com")
    first = create_lead(client)
    second = create_lead(client, monthly_bill="2000")
    signup(client, "b@example.com")
    create_lead(client)
    signup_again = client.post(
        "/api/auth/login", headers=CSRF, json={"identifier": "a@example.com", "password": PASSWORD}
    )
    assert signup_again.status_code == 200
    mine = client.get("/api/leads/mine").json()
    assert [lead["id"] for lead in mine] == [second["id"], first["id"]]


def test_someone_elses_lead_is_404(client, ai):
    signup(client, "owner1@example.com")
    lead = create_lead(client)
    signup(client, "owner2@example.com")
    assert client.get(f"/api/leads/{lead['id']}").status_code == 404


# --- Qualification on confirmation: the brief's three sample leads ---


def test_prashant_is_qualified_for_a_survey_visit(client, ai, db_session):
    signup(client, "prashant@example.com")
    lead = create_lead(client)
    after = upload_and_confirm(
        client,
        lead["id"],
        {
            "avg_monthly_units": "340",
            "bill_amount": "3200",
            "sanctioned_load_kw": "3",
        },
    )
    assert after["status"] == "survey_pending"
    assert after["next_action"] == "survey_visit"
    assert after["recommended_kw"] == "3"
    assert after["recommendation_status"] == "provisional"
    row = db_session.get(Lead, lead["id"])
    assert row.score.value == "high" and row.score_reasons == []


def test_rohit_tenant_gets_a_call_and_no_size(client, ai, db_session):
    signup(client, "rohit@example.com")
    lead = create_lead(client, ownership="tenant", monthly_bill="1900")
    after = upload_and_confirm(
        client, lead["id"], {"avg_monthly_units": "210", "bill_amount": "1900"}
    )
    assert (after["status"], after["next_action"], after["recommended_kw"]) == (
        "call_pending",
        "call",
        None,
    )
    assert [r["code"] for r in db_session.get(Lead, lead["id"]).score_reasons] == ["tenant"]


def test_ayesha_small_bill_gets_a_call_with_plain_reason(client, ai, db_session):
    signup(client, "ayesha@example.com")
    lead = create_lead(client, monthly_bill="650", roof_area_sqft="200")
    after = upload_and_confirm(
        client, lead["id"], {"avg_monthly_units": "85", "bill_amount": "650"}
    )
    assert (after["next_action"], after["recommended_kw"]) == ("call", "1")
    assert db_session.get(Lead, lead["id"]).score_reasons == [
        {"code": "bill_below_threshold", "value": "650", "threshold": "1000", "source": "confirmed"}
    ]


def test_zero_units_bill_gets_a_call(client, ai):
    signup(client, "zero@example.com")
    lead = create_lead(client)
    after = upload_and_confirm(
        client, lead["id"], {"avg_monthly_units": "0", "bill_amount": "1500"}
    )
    assert (after["next_action"], after["recommended_kw"]) == ("call", None)


def test_lead_shows_its_latest_reading(client, ai):
    signup(client, "r@example.com")
    lead = create_lead(client)
    up = client.post(
        f"/api/leads/{lead['id']}/bills",
        headers=CSRF,
        files={"file": ("bill.jpg", (BILLS / "clear.jpg").read_bytes())},
    )
    detail = client.get(f"/api/leads/{lead['id']}").json()
    assert detail["latest_reading"] == {"id": up.json()["id"], "status": "needs_review"}
    assert detail["current_reading"] is None  # not confirmed yet


# --- Preferred language ---


def test_preferred_locale_is_saved(client, ai):
    signup(client, "lang@example.com")
    res = client.patch("/api/auth/me", headers=CSRF, json={"preferred_locale": "mr"})
    assert res.status_code == 200 and res.json()["preferred_locale"] == "mr"
    assert client.get("/api/auth/me").json()["preferred_locale"] == "mr"
    bad = client.patch("/api/auth/me", headers=CSRF, json={"preferred_locale": "fr"})
    assert bad.status_code == 422


def test_numbers_on_the_way_out_are_plain(client, ai):
    signup(client, "plain@example.com")
    lead = create_lead(client, roof_area_sqft="450.00", monthly_bill="3200.50")
    assert lead["roof_area_sqft"] == "450" and lead["declared_monthly_bill"] == "3200.5"
    assert D(lead["declared_monthly_bill"]) == D("3200.5")


# --- Status only moves forward (review M4 #1) ---


def test_confirming_an_older_reading_after_qualification_is_refused(client, ai):
    signup(client, "fwd@example.com")
    lead = create_lead(client)
    older = client.post(
        f"/api/leads/{lead['id']}/bills",
        headers=CSRF,
        files={"file": ("bill.jpg", (BILLS / "clear.jpg").read_bytes())},
    ).json()
    newer = client.post(
        f"/api/leads/{lead['id']}/bills",
        headers=CSRF,
        files={"file": ("bill.png", (BILLS / "tiny.png").read_bytes())},
    )
    assert newer.status_code in (200, 202)
    res = client.post(
        f"/api/bills/{newer.json()['id']}/confirm",
        headers=CSRF,
        json={"avg_monthly_units": "340", "bill_amount": "3200"},
    )
    assert res.status_code == 200, res.text
    assert client.get(f"/api/leads/{lead['id']}").json()["status"] == "survey_pending"

    stale = client.post(
        f"/api/bills/{older['id']}/confirm",
        headers=CSRF,
        json={"avg_monthly_units": "100", "bill_amount": "700"},
    )
    assert (stale.status_code, stale.json()["error"]["code"]) == (409, "LEAD_LOCKED")
    detail = client.get(f"/api/leads/{lead['id']}").json()
    assert (
        detail["status"] == "survey_pending"
        and detail["current_reading"]["id"] == newer.json()["id"]
    )


def test_a_late_read_never_pulls_a_qualified_lead_back(client, ai, db_session):
    """process_reading/sweep_if_stale finishing an older reading must not undo qualification."""
    from app.services.bill_reading import _back_to_review

    signup(client, "sweep@example.com")
    lead = create_lead(client)
    upload_and_confirm(client, lead["id"], {"avg_monthly_units": "340", "bill_amount": "3200"})
    _back_to_review(db_session, lead["id"])
    assert db_session.get(Lead, lead["id"]).status.value == "survey_pending"


# --- Editing home details from the bill step (user request) ---


def test_homeowner_can_edit_details_before_the_bill_is_confirmed(client, ai):
    signup(client, "edit@example.com")
    lead = create_lead(client)
    edit = {**HOME, "roof_area_sqft": "600", "monthly_bill": "2800", "ownership": "owner"}
    res = client.patch(f"/api/leads/{lead['id']}", headers=CSRF, json=edit)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["roof_area_sqft"] == "600" and body["declared_monthly_bill"] == "2800"
    assert body["code"] == lead["code"]  # same lead, not a new one
    bad = client.patch(f"/api/leads/{lead['id']}", headers=CSRF, json={**edit, "pincode": "12"})
    assert bad.status_code == 422


def test_details_are_locked_once_the_bill_is_confirmed(client, ai):
    signup(client, "locked@example.com")
    lead = create_lead(client)
    upload_and_confirm(client, lead["id"], {"avg_monthly_units": "340", "bill_amount": "3200"})
    res = client.patch(f"/api/leads/{lead['id']}", headers=CSRF, json=HOME)
    assert (res.status_code, res.json()["error"]["code"]) == (409, "LEAD_LOCKED")


def test_cannot_edit_someone_elses_lead(client, ai):
    signup(client, "first@example.com")
    lead = create_lead(client)
    signup(client, "second@example.com")
    assert client.patch(f"/api/leads/{lead['id']}", headers=CSRF, json=HOME).status_code == 404
