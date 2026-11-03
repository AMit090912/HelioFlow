"""Bills API: upload → background AI reading → poll → confirm (ARCHITECTURE §5, §6, §15.2, §15.3).

AI providers are scripted fakes injected through app.state, so no test ever calls Groq or Gemini.
"""

from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import BillReading, Lead, User
from app.models.enums import Ownership, PropertyType, RoofType, UserRole
from app.services.ai.providers import ProviderError
from tests.unit.ai.test_ai import GOOD, Scripted

BILLS = Path(__file__).resolve().parents[1] / "fixtures" / "bills"
CSRF = {"X-HF-CSRF": "1"}
PASSWORD = "sunrise-roof-42"


def make_owner(db: Session, email: str) -> tuple[User, Lead]:
    user = User(
        role=UserRole.homeowner,
        full_name="Owner",
        email=email,
        password_hash=hash_password(PASSWORD),
    )
    db.add(user)
    db.flush()
    lead = Lead(
        code=f"LD-{email[:4]}",
        homeowner_id=user.id,
        ownership=Ownership.owner,
        property_type=PropertyType.home,
        roof_type=RoofType.rcc_flat,
        roof_area_sqft=D("450"),
        declared_monthly_bill=D("3200"),
        pincode="440010",
        consent_at=datetime.now(UTC),
        consent_version="v1",
    )
    db.add(lead)
    db.flush()
    return user, lead


def sign_in(client: TestClient, email: str) -> None:
    client.cookies.clear()
    res = client.post(
        "/api/auth/login", json={"identifier": email, "password": PASSWORD}, headers=CSRF
    )
    assert res.status_code == 200


@pytest.fixture
def ai(client: TestClient, db_session: Session):
    """Wire the app to the test session and a scripted provider chain."""
    from seed import run as seed

    seed(db_session, "seed-pass-for-tests")  # confirming a bill scores the lead (needs settings)
    state = {"providers": [Scripted("groq", GOOD)]}
    client.app.state.session_factory = lambda: nullcontext(db_session)
    client.app.state.ai_providers = lambda sha: state["providers"]
    return state


@pytest.fixture
def owner(client: TestClient, db_session: Session, ai):
    user, lead = make_owner(db_session, "prashant@example.com")
    sign_in(client, "prashant@example.com")
    return user, lead


def upload(client, lead, name, content=None):
    data = content if content is not None else (BILLS / name).read_bytes()
    return client.post(f"/api/leads/{lead.id}/bills", files={"file": (name, data)}, headers=CSRF)


# --- Happy path ---


def test_upload_reads_the_bill_in_the_background(client, owner, ai):
    _, lead = owner
    res = upload(client, lead, "clear.jpg")
    assert res.status_code == 202
    reading_id = res.json()["id"]
    body = client.get(f"/api/bills/{reading_id}").json()
    assert body["status"] == "needs_review"
    assert body["source_path"] == "vision"
    assert body["provider"] == "groq" and body["is_demo"] is False
    assert body["ai"]["current_units"] == {"value": 340, "confidence": 0.96}
    assert body["suggested_avg_monthly_units"] == "340"  # plain, like every number
    assert body["suggested_method"] == "history_mean"
    assert body["flags"] == {}
    assert body["attempts"][0]["outcome"] == "ok"


def test_text_pdf_is_read_as_text(client, owner, ai):
    groq = Scripted("groq", GOOD)
    ai["providers"] = [groq]
    _, lead = owner
    reading_id = upload(client, lead, "text.pdf").json()["id"]
    assert client.get(f"/api/bills/{reading_id}").json()["source_path"] == "pdf_text"
    assert groq.calls == 1


def test_scanned_pdf_is_rendered_for_vision(client, owner):
    _, lead = owner
    reading_id = upload(client, lead, "scanned.pdf").json()["id"]
    body = client.get(f"/api/bills/{reading_id}").json()
    assert (body["source_path"], body["status"], body["kind"]) == ("vision", "needs_review", "pdf")


def test_same_file_twice_reuses_the_reading(client, owner, ai):
    """Review Focus 4: no second AI call for the same file on the same lead."""
    groq = Scripted("groq", GOOD, GOOD)
    ai["providers"] = [groq]
    _, lead = owner
    first = upload(client, lead, "clear.jpg")
    second = upload(client, lead, "clear.jpg")
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert groq.calls == 1


def test_blurry_photo_needs_reupload_without_an_ai_call(client, owner, ai):
    groq = Scripted("groq", GOOD)
    ai["providers"] = [groq]
    _, lead = owner
    body = upload(client, lead, "blurry.jpg").json()
    assert body["status"] == "needs_reupload"
    assert "blurry" in body["quality"]["reasons"]
    assert groq.calls == 0


def test_unreadable_with_no_units_asks_for_a_reupload(client, owner, ai):
    nothing = {
        **GOOD,
        "legibility": "poor",
        "monthly_units": {"value": None, "confidence": 0},
        "current_units": {"value": None, "confidence": 0},
    }
    ai["providers"] = [Scripted("groq", nothing)]
    _, lead = owner
    reading_id = upload(client, lead, "clear.jpg").json()["id"]
    body = client.get(f"/api/bills/{reading_id}").json()
    assert body["status"] == "needs_reupload"
    assert "legibility_poor" in body["flags"]["document"]


def test_values_decide_not_the_models_opinion_of_the_photo(client, owner, ai):
    """A partial or faded photo the model calls "poor"/"not a bill" but whose units it read
    goes to review — the person checks the values instead of re-uploading (user report)."""
    doubtful = {**GOOD, "legibility": "poor", "is_electricity_bill": False}
    ai["providers"] = [Scripted("groq", doubtful)]
    _, lead = owner
    reading_id = upload(client, lead, "clear.jpg").json()["id"]
    body = client.get(f"/api/bills/{reading_id}").json()
    assert body["status"] == "needs_review"
    assert body["suggested_avg_monthly_units"] == "340"


# --- Fallbacks: the lead is never lost ---


def test_gemini_takes_over_when_groq_fails(client, owner, ai):
    ai["providers"] = [Scripted("groq", ProviderError("auth", 401)), Scripted("gemini", GOOD)]
    _, lead = owner
    reading_id = upload(client, lead, "clear.jpg").json()["id"]
    body = client.get(f"/api/bills/{reading_id}").json()
    assert body["provider"] == "gemini"
    assert [a["provider"] for a in body["attempts"]] == ["groq", "gemini"]


def test_both_failing_goes_to_manual_entry_and_confirm_still_works(client, owner, ai):
    ai["providers"] = [
        Scripted("groq", ProviderError("auth", 401)),
        Scripted("gemini", ProviderError("invalid_response")),
    ]
    _, lead = owner
    reading_id = upload(client, lead, "clear.jpg").json()["id"]
    assert client.get(f"/api/bills/{reading_id}").json()["status"] == "failed_manual"

    res = client.post(
        f"/api/bills/{reading_id}/confirm",
        headers=CSRF,
        json={
            "avg_monthly_units": "340",
            "bill_amount": "3200",
            "sanctioned_load_kw": "3",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "confirmed" and body["source_path"] == "manual"
    assert body["confirmed"]["avg_monthly_units"] == "340"


def test_stale_processing_reading_becomes_manual(client, owner, ai, db_session):
    """Review Focus 5: a reading orphaned by a restart doesn't spin forever."""
    ai["providers"] = []  # background job records no AI success
    _, lead = owner
    reading_id = upload(client, lead, "clear.jpg").json()["id"]
    reading = db_session.get(BillReading, reading_id)
    reading.status = "processing"
    reading.processing_started_at = datetime.now(UTC) - timedelta(minutes=3)
    db_session.flush()
    body = client.get(f"/api/bills/{reading_id}").json()
    assert body["status"] == "failed_manual"
    assert body["attempts"][-1]["error_code"] == "stale"


# --- Confirmation keeps AI and human values apart ---


def test_confirm_records_what_the_person_changed(client, owner, db_session):
    _, lead = owner
    reading_id = upload(client, lead, "clear.jpg").json()["id"]
    res = client.post(
        f"/api/bills/{reading_id}/confirm",
        headers=CSRF,
        json={
            "consumer_number": "410012345678",
            "tariff_category": "LT-I Residential",
            "sanctioned_load_kw": "5",
            "avg_monthly_units": "340",
            "bill_amount": "3200",
            "fixed_charge_monthly": "130",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["edited_fields"] == ["sanctioned_load_kw"]
    assert body["ai"]["sanctioned_load_kw"]["value"] == "3.0"  # AI value preserved
    assert body["confirmed"]["sanctioned_load_kw"] == "5"
    assert db_session.get(Lead, lead.id).current_bill_reading_id is not None


@pytest.mark.parametrize(
    "bad",
    [
        {"avg_monthly_units": "-1", "bill_amount": "3200"},
        {"avg_monthly_units": "340", "bill_amount": "0"},
        {"avg_monthly_units": "340", "bill_amount": "3200", "sanctioned_load_kw": "500"},
        {"bill_amount": "3200"},
    ],
)
def test_confirm_validates_values(client, owner, bad):
    _, lead = owner
    reading_id = upload(client, lead, "clear.jpg").json()["id"]
    res = client.post(f"/api/bills/{reading_id}/confirm", headers=CSRF, json=bad)
    assert res.status_code == 422


# --- Review fixes: roles, races, validation, lead state ---


def make_staff(db, email="sales@example.com"):
    db.add(
        User(
            role=UserRole.sales,
            full_name="Sales",
            email=email,
            password_hash=hash_password(PASSWORD),
        )
    )
    db.flush()


def test_staff_cannot_upload_or_confirm(client, owner, db_session):
    """§4: upload and confirm are the homeowner's own actions; staff view only."""
    _, lead = owner
    reading_id = upload(client, lead, "clear.jpg").json()["id"]
    make_staff(db_session)
    sign_in(client, "sales@example.com")
    assert upload(client, lead, "tiny.png").status_code == 403
    res = client.post(
        f"/api/bills/{reading_id}/confirm",
        headers=CSRF,
        json={"avg_monthly_units": "340", "bill_amount": "3200"},
    )
    assert res.status_code == 403


def test_late_ai_result_never_overwrites_a_confirmed_reading(client, owner, ai, db_session):
    """If the reading was swept/confirmed while the AI was still working, the job backs off."""
    _, lead = owner

    class LateConfirm(Scripted):
        def extract(self, *, images, text):
            reading = db_session.query(BillReading).filter_by(lead_id=lead.id).one()
            reading.status = "confirmed"
            db_session.flush()
            return super().extract(images=images, text=text)

    ai["providers"] = [LateConfirm("groq", GOOD)]
    reading_id = upload(client, lead, "clear.jpg").json()["id"]
    reading = db_session.get(BillReading, reading_id)
    assert reading.status.value == "confirmed"
    assert reading.ai_values is None


def test_confirm_revalidates_ai_values_it_keeps(client, owner, ai):
    """An AI value the person didn't override must still pass the confirm rules."""
    bad_load = {**GOOD, "sanctioned_load_kw": {"value": 3000, "confidence": 0.9}}
    ai["providers"] = [Scripted("groq", bad_load)]
    _, lead = owner
    reading_id = upload(client, lead, "clear.jpg").json()["id"]
    res = client.post(
        f"/api/bills/{reading_id}/confirm",
        headers=CSRF,
        json={"avg_monthly_units": "340", "bill_amount": "3200"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_monthly_units_must_be_sane(client, owner):
    _, lead = owner
    reading_id = upload(client, lead, "clear.jpg").json()["id"]
    res = client.post(
        f"/api/bills/{reading_id}/confirm",
        headers=CSRF,
        json={
            "avg_monthly_units": "340",
            "bill_amount": "3200",
            "monthly_units": [340, -5],
        },
    )
    assert res.status_code == 422


def test_double_submitted_upload_still_returns_one_reading(client, owner, ai, monkeypatch):
    """Two concurrent uploads of one file: the unique index decides, nobody gets a 500."""
    from app.services import bill_reading

    _, lead = owner
    first = upload(client, lead, "clear.jpg").json()["id"]
    monkeypatch.setattr(bill_reading, "_existing_reading", lambda *a, **k: None)  # lose the race
    second = upload(client, lead, "clear.jpg")
    assert second.status_code == 200
    assert second.json()["id"] == first


def test_reupload_after_ai_outage_tries_again(client, owner, ai):
    ai["providers"] = [Scripted("groq", ProviderError("server", 503), ProviderError("server", 503))]
    _, lead = owner
    reading_id = upload(client, lead, "clear.jpg").json()["id"]
    assert client.get(f"/api/bills/{reading_id}").json()["status"] == "failed_manual"
    ai["providers"] = [Scripted("groq", GOOD)]
    again = upload(client, lead, "clear.jpg")
    assert again.status_code == 202 and again.json()["id"] == reading_id
    assert client.get(f"/api/bills/{reading_id}").json()["status"] == "needs_review"


def test_confirmed_reading_cannot_be_silently_reconfirmed(client, owner):
    _, lead = owner
    reading_id = upload(client, lead, "clear.jpg").json()["id"]
    values = {"avg_monthly_units": "340", "bill_amount": "3200"}
    assert (
        client.post(f"/api/bills/{reading_id}/confirm", headers=CSRF, json=values).status_code
        == 200
    )
    again = client.post(f"/api/bills/{reading_id}/confirm", headers=CSRF, json=values)
    assert (again.status_code, again.json()["error"]["code"]) == (409, "READING_ALREADY_CONFIRMED")


def test_upload_is_refused_once_the_lead_has_moved_on(client, owner, db_session):
    from app.models.enums import LeadStatus

    _, lead = owner
    lead.status = LeadStatus.quoted
    db_session.flush()
    res = upload(client, lead, "clear.jpg")
    assert (res.status_code, res.json()["error"]["code"]) == (409, "LEAD_LOCKED")


def test_failed_reading_moves_the_lead_to_review(client, owner, ai, db_session):
    ai["providers"] = [Scripted("groq", ProviderError("auth", 401))]
    _, lead = owner
    upload(client, lead, "clear.jpg")
    assert db_session.get(Lead, lead.id).status.value == "bill_review"


def test_oversized_request_is_refused_before_parsing(client, owner):
    _, lead = owner
    res = client.post(
        f"/api/leads/{lead.id}/bills",
        headers={**CSRF, "content-length": str(50 * 1024 * 1024)},
        content=b"x",
    )
    assert (res.status_code, res.json()["error"]["code"]) == (413, "FILE_TOO_LARGE")


# --- Rejections at the gate ---


def test_renamed_executable_is_415(client, owner):
    _, lead = owner
    res = upload(client, lead, "fake.jpg")
    assert (res.status_code, res.json()["error"]["code"]) == (415, "FILE_TYPE_UNSUPPORTED")


def test_oversized_upload_is_413(client, owner):
    _, lead = owner
    res = upload(client, lead, "big.jpg", content=b"\xff\xd8\xff" + b"0" * (10 * 1024 * 1024))
    assert (res.status_code, res.json()["error"]["code"]) == (413, "FILE_TOO_LARGE")


def test_encrypted_pdf_is_422(client, owner):
    _, lead = owner
    res = upload(client, lead, "encrypted.pdf")
    assert (res.status_code, res.json()["error"]["code"]) == (422, "PDF_ENCRYPTED")


# --- Access control and privacy ---


def test_other_homeowners_cannot_see_or_touch_the_bill(client, owner, db_session):
    _, lead = owner
    reading_id = upload(client, lead, "clear.jpg").json()["id"]
    make_owner(db_session, "someone@example.com")
    sign_in(client, "someone@example.com")
    assert client.get(f"/api/bills/{reading_id}").status_code == 404
    assert client.get(f"/api/bills/{reading_id}/preview").status_code == 404
    assert (
        client.post(
            f"/api/bills/{reading_id}/confirm",
            headers=CSRF,
            json={"avg_monthly_units": "1", "bill_amount": "1"},
        ).status_code
        == 404
    )
    assert upload(client, lead, "clear.jpg").status_code == 404


def test_staff_can_open_any_bill(client, owner, db_session):
    _, lead = owner
    reading_id = upload(client, lead, "clear.jpg").json()["id"]
    db_session.add(
        User(
            role=UserRole.sales,
            full_name="Sales",
            email="sales@example.com",
            password_hash=hash_password(PASSWORD),
        )
    )
    db_session.flush()
    sign_in(client, "sales@example.com")
    assert client.get(f"/api/bills/{reading_id}").status_code == 200


def test_preview_is_private_png(client, owner):
    _, lead = owner
    reading_id = upload(client, lead, "clear.jpg").json()["id"]
    res = client.get(f"/api/bills/{reading_id}/preview")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert "no-store" in res.headers["cache-control"]
    assert res.content.startswith(b"\x89PNG")
    client.cookies.clear()
    assert client.get(f"/api/bills/{reading_id}/preview").status_code == 401


def test_upload_is_rate_limited(client, owner):
    _, lead = owner
    for i in range(10):
        upload(client, lead, f"x{i}.jpg", content=b"not-an-image")
    res = upload(client, lead, "clear.jpg")
    assert (res.status_code, res.json()["error"]["code"]) == (429, "RATE_LIMITED")


def test_multi_month_bill_is_confirmed_per_month(client, db_session, ai):
    """A 93-day spot bill: the form is pre-filled with per-month figures, and confirming without
    edits stores those, not the 3-month totals (A-30)."""
    from tests.unit.ai.test_receipt_bills import SPOT_93_DAYS

    ai["providers"] = [Scripted("groq", SPOT_93_DAYS)]
    owner, lead = make_owner(db_session, "spot@example.com")
    sign_in(client, "spot@example.com")
    up = client.post(
        f"/api/leads/{lead.id}/bills",
        headers=CSRF,
        files={"file": ("bill.jpg", (BILLS / "clear.jpg").read_bytes())},
    ).json()
    reading = client.get(f"/api/bills/{up['id']}").json()
    assert reading["billing_days"] == 93
    assert reading["suggested_method"] == "period_normalised"
    assert reading["suggested_avg_monthly_units"] == "568.1"
    assert reading["suggested_bill_amount"] == "4211.84"
    assert reading["suggested_fixed_charge"] == "78.49"
    assert reading["flags"]["current_units"] == ["long_billing_period"]
    # What the form sends when the person accepts the pre-filled values unchanged.
    form = {
        "avg_monthly_units": reading["suggested_avg_monthly_units"],
        "bill_amount": reading["suggested_bill_amount"],
        "fixed_charge_monthly": reading["suggested_fixed_charge"],
    }
    res = client.post(f"/api/bills/{up['id']}/confirm", headers=CSRF, json=form)
    assert res.status_code == 200, res.text
    confirmed = res.json()
    assert confirmed["edited_fields"] == []  # per-month figures are the proposal, not an edit
    assert confirmed["confirmed"]["avg_monthly_units"] == "568.1"
    assert confirmed["confirmed"]["bill_amount"] == "4211.84"
    assert confirmed["confirmed"]["fixed_charge_monthly"] == "78.49"
