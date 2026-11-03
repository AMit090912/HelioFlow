"""Quote builder preview, send (immutable snapshot), supersede and accept (§3.8, §8, §10, §11)."""

import re
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models import Lead, Notification, PriceRule, Quote
from tests.integration.test_bills_api import CSRF, make_staff, sign_in
from tests.integration.test_leads_api import (  # noqa: F401  (ai is a fixture)
    ai,
    create_lead,
    signup,
    upload_and_confirm,
)

OWNER = "quote-owner@example.com"
DESK = "quote-desk@example.com"


def verify(client: TestClient, lead_id: str, roof="450", load="5") -> None:
    body = {"roof_area_sqft": roof, "via": "survey"}
    if load is not None:
        body["sanctioned_load_kw"] = load
    res = client.post(f"/api/staff/leads/{lead_id}/verification", headers=CSRF, json=body)
    assert res.status_code == 200, res.text


# Prashant from the brief: only units and bill are known, so the bill's other values are
# cleared explicitly (an omitted field would keep the AI's reading of the sample bill).
PRASHANT = {
    "avg_monthly_units": "340",
    "bill_amount": "3200",
    "sanctioned_load_kw": None,
    "fixed_charge_monthly": None,
}


@pytest.fixture
def lead(client: TestClient, db_session: Session, ai):  # noqa: F811
    """Prashant-like lead, confirmed by the homeowner; staff signed in afterwards."""
    signup(client, OWNER)
    created = create_lead(client)
    upload_and_confirm(client, created["id"], PRASHANT)
    make_staff(db_session, DESK)
    sign_in(client, DESK)
    return created["id"]


def preview(client, lead_id, overrides=()):
    return client.post(
        f"/api/staff/leads/{lead_id}/quote-preview",
        headers=CSRF,
        json={"overrides": list(overrides)},
    )


def send(client, lead_id, overrides=()):
    return client.post(
        f"/api/staff/leads/{lead_id}/quotes", headers=CSRF, json={"overrides": list(overrides)}
    )


def option(body, kw):
    return next(o for o in body["options"] if o["kw"] == kw)


# --- Preview ---


def test_preview_offers_2_3_4_for_prashant(client, lead):
    verify(client, lead)
    res = preview(client, lead)
    assert res.status_code == 200, res.text
    body = res.json()
    assert [o["kw"] for o in body["options"]] == ["2", "3", "4"]
    assert body["recommended_kw"] == "3" and body["provisional_kw"] == "3"
    three = option(body, "3")
    assert three["recommended"] is True
    assert three["gross"] == "180000" and three["net"] == "102000"
    assert three["subsidy"]["amount"] == "78000"
    assert three["savings"]["annual_savings"] == "33909"
    assert three["savings"]["fixed_charge_source"] == "default"
    assert three["payback"] == {"years": "3.0", "status": "ok"}
    assert body["sanctioned_load"] == {"value": "5", "source": "staff"}


def test_load_3kw_removes_4kw(client, lead):
    verify(client, lead, load="3")
    body = preview(client, lead).json()
    assert [o["kw"] for o in body["options"]] == ["2", "3"]
    assert {"kw": "4", "reason": "sanctioned_load"} in body["removed"]


def test_tiny_roof_has_no_options(client, lead):
    verify(client, lead, roof="80")
    res = preview(client, lead)
    assert (res.status_code, res.json()["error"]["code"]) == (422, "NO_OPTION_FITS")
    assert send(client, lead).status_code == 422


def test_preview_requires_verified_roof(client, lead):
    res = preview(client, lead)
    assert (res.status_code, res.json()["error"]["code"]) == (422, "ROOF_NOT_VERIFIED")


def test_preview_requires_a_known_sanctioned_load(client, lead):
    verify(client, lead, load=None)  # the confirmed bill had no load either
    res = preview(client, lead)
    assert (res.status_code, res.json()["error"]["code"]) == (422, "SANCTIONED_LOAD_UNKNOWN")


def test_preview_applies_overrides_without_reason(client, lead):
    verify(client, lead)
    body = preview(client, lead, [{"field": "fixed_charge_monthly", "value": "180"}]).json()
    assert option(body, "3")["savings"]["fixed_charge"] == "180"
    assert option(body, "3")["savings"]["fixed_charge_source"] == "override"
    bad = preview(client, lead, [{"field": "usable_generation_pct", "value": "1.5"}])
    assert (bad.status_code, bad.json()["error"]["code"]) == (422, "INVALID_INPUT")


def test_homeowner_cannot_preview_or_send(client, lead):
    sign_in(client, OWNER)
    assert preview(client, lead).status_code == 403
    assert send(client, lead).status_code == 403


# --- Send ---


def test_send_requires_override_reason(client, lead, db_session):
    verify(client, lead)
    override = {"field": "fixed_charge_monthly", "value": "180"}
    res = send(client, lead, [override])
    assert (res.status_code, res.json()["error"]["code"]) == (422, "OVERRIDE_REASON_REQUIRED")

    ok = send(client, lead, [{**override, "reason": "Bill shows ₹180 fixed charge."}])
    assert ok.status_code == 201, ok.text
    snap = db_session.get(Quote, ok.json()["id"]).snapshot
    [recorded] = snap["overrides"]
    assert recorded["field"] == "fixed_charge_monthly"
    assert (recorded["from"], recorded["to"]) == ("150", "180")
    assert recorded["reason"] == "Bill shows ₹180 fixed charge." and recorded["by"]


def test_send_creates_numbered_quote_event_and_notification(client, lead, db_session):
    verify(client, lead)
    res = send(client, lead)
    assert res.status_code == 201, res.text
    quote = res.json()
    assert re.fullmatch(r"HF-Q-\d{4}-\d{6}", quote["number"])
    assert quote["status"] == "sent" and quote["recommended_kw"] == "3"
    row = db_session.get(Quote, quote["id"])
    snap = row.snapshot
    assert snap["calc_version"] == "calc-1.0.0"
    assert snap["price_rules_used"][0]["price_per_kw"] == "60000"
    assert snap["subsidy_rule"]["cap_amount"] == "78000"
    assert snap["inputs"]["verified_roof_sqft"] == "450"
    assert snap["inputs"]["sanctioned_load_source"] == "staff"
    assert snap["settings"]["generation_kwh_per_kw_year"] == "1400"
    lead_row = db_session.get(Lead, lead)
    assert lead_row.status.value == "quoted"
    [note] = db_session.execute(
        select(Notification).where(Notification.lead_id == lead_row.id)
    ).scalars()
    assert note.type.value == "quote_sent" and note.delivery_status == "simulated"
    assert quote["number"] in note.message and "1,02,000" in note.message
    assert "•" in note.recipient_masked
    detail = client.get(f"/api/staff/leads/{lead}").json()
    assert detail["status"] == "quoted" and detail["quotes"][0]["number"] == quote["number"]
    assert detail["events"][0]["kind"] == "quote_sent"


def test_notification_uses_homeowner_language(client, lead, db_session):
    sign_in(client, OWNER)
    client.patch("/api/auth/me", headers=CSRF, json={"preferred_locale": "mr"})
    sign_in(client, DESK)
    verify(client, lead)
    send(client, lead)
    note = db_session.execute(select(Notification)).scalars().one()
    assert note.locale.value == "mr" and "कोटेशन" in note.message


def test_quote_survives_rule_changes(client, lead, db_session):
    verify(client, lead)
    quote_id = send(client, lead).json()["id"]
    today = date.today()
    rule = db_session.execute(select(PriceRule)).scalars().one()
    rule.effective_to = today - timedelta(days=1)
    db_session.flush()
    db_session.add(
        PriceRule(
            min_kw=Decimal("1"),
            max_kw=Decimal("10"),
            price_per_kw=Decimal("70000"),
            gst_inclusive=True,
            effective_from=today,
            note="test: price rise",
        )
    )
    db_session.flush()
    view = client.get(f"/api/quotes/{quote_id}").json()
    assert option(view, "3")["gross"] == "180000"
    assert option(preview(client, lead).json(), "3")["gross"] == "210000"  # new quotes see it


def test_new_quote_supersedes_and_old_cannot_be_accepted(client, lead, db_session):
    verify(client, lead)
    first = send(client, lead).json()
    second = send(client, lead).json()
    assert first["number"] != second["number"]
    old = db_session.get(Quote, first["id"])
    db_session.refresh(old)
    assert old.status.value == "superseded" and str(old.superseded_by_quote_id) == second["id"]
    sign_in(client, OWNER)
    res = client.post(f"/api/quotes/{first['id']}/accept", headers=CSRF, json={"selected_kw": "3"})
    assert (res.status_code, res.json()["error"]["code"]) == (409, "QUOTE_SUPERSEDED")
    mine = client.get(f"/api/leads/{lead}").json()
    assert mine["current_quote"] == {"id": second["id"], "status": "sent"}


def test_accept_only_offered_option(client, lead, db_session):
    verify(client, lead)
    quote_id = send(client, lead).json()["id"]
    sign_in(client, OWNER)
    bad = client.post(f"/api/quotes/{quote_id}/accept", headers=CSRF, json={"selected_kw": "7"})
    assert (bad.status_code, bad.json()["error"]["code"]) == (422, "OPTION_NOT_OFFERED")
    ok = client.post(f"/api/quotes/{quote_id}/accept", headers=CSRF, json={"selected_kw": "3"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "accepted" and ok.json()["selected_kw"] == "3"
    assert client.get(f"/api/leads/{lead}").json()["status"] == "accepted"
    again = client.post(f"/api/quotes/{quote_id}/accept", headers=CSRF, json={"selected_kw": "2"})
    assert (again.status_code, again.json()["error"]["code"]) == (409, "QUOTE_ALREADY_ACCEPTED")
    sign_in(client, DESK)
    assert send(client, lead).status_code == 409  # accepted leads are not re-quoted


def test_staff_cannot_accept(client, lead):
    verify(client, lead)
    quote_id = send(client, lead).json()["id"]
    res = client.post(f"/api/quotes/{quote_id}/accept", headers=CSRF, json={"selected_kw": "3"})
    assert res.status_code == 403


def test_snapshot_cannot_be_updated(client, lead, db_session):
    verify(client, lead)
    quote_id = send(client, lead).json()["id"]
    with pytest.raises(DBAPIError, match="QUOTE_IMMUTABLE"):
        with db_session.begin_nested():
            db_session.execute(update(Quote).where(Quote.id == quote_id).values(snapshot={}))


def test_foreign_quote_is_404(client, lead):
    verify(client, lead)
    quote_id = send(client, lead).json()["id"]
    signup(client, "stranger@example.com")
    assert client.get(f"/api/quotes/{quote_id}").status_code == 404
    res = client.post(f"/api/quotes/{quote_id}/accept", headers=CSRF, json={"selected_kw": "3"})
    assert res.status_code == 404


def test_tenant_cannot_be_quoted(client, db_session, ai):  # noqa: F811
    signup(client, "tenant@example.com")
    created = create_lead(client, ownership="tenant")
    upload_and_confirm(client, created["id"], {"avg_monthly_units": "210", "bill_amount": "1900"})
    make_staff(db_session, DESK)
    sign_in(client, DESK)
    verify(client, created["id"])
    res = preview(client, created["id"])
    assert (res.status_code, res.json()["error"]["code"]) == (422, "NOT_QUOTABLE_TENANT")


def test_lead_mine_shows_current_quote(client, lead):
    sign_in(client, OWNER)
    assert client.get(f"/api/leads/{lead}").json()["current_quote"] is None
    sign_in(client, DESK)
    verify(client, lead)
    quote_id = send(client, lead).json()["id"]
    sign_in(client, OWNER)
    assert client.get(f"/api/leads/{lead}").json()["current_quote"] == {
        "id": quote_id,
        "status": "sent",
    }
    view = client.get(f"/api/quotes/{quote_id}").json()
    assert view["lead_code"].startswith("LD-") and len(view["options"]) == 3


# --- Review fixes ---


def test_homeowner_view_hides_staff_override_notes(client, lead):
    verify(client, lead)
    override = {
        "field": "fixed_charge_monthly",
        "value": "180",
        "reason": "Internal: bill shows 180",
    }
    quote_id = send(client, lead, [override]).json()["id"]
    staff_view = client.get(f"/api/quotes/{quote_id}").json()
    assert staff_view["overrides"][0]["reason"] == "Internal: bill shows 180"
    sign_in(client, OWNER)
    mine = client.get(f"/api/quotes/{quote_id}").json()
    assert mine["overrides"] == [{"field": "fixed_charge_monthly", "from": "150", "to": "180"}]


def test_quote_view_carries_lead_status_for_closed_leads(client, lead):
    verify(client, lead)
    quote_id = send(client, lead).json()["id"]
    client.post(
        f"/api/staff/leads/{lead}/close", headers=CSRF, json={"reason": "Chose another installer"}
    )
    sign_in(client, OWNER)
    view = client.get(f"/api/quotes/{quote_id}").json()
    assert view["lead_status"] == "closed_lost" and view["status"] == "sent"


def test_zero_fixed_charge_on_bill_is_recorded_as_zero(client, db_session, ai):  # noqa: F811
    signup(client, "zero-fixed@example.com")
    created = create_lead(client)
    upload_and_confirm(client, created["id"], {**PRASHANT, "fixed_charge_monthly": "0"})
    make_staff(db_session, DESK)
    sign_in(client, DESK)
    verify(client, created["id"])
    override = {"field": "fixed_charge_monthly", "value": "100", "reason": "Checked with DISCOM"}
    quote = send(client, created["id"], [override]).json()
    assert quote["overrides"][0]["from"] == "0"
    rate = {"field": "savings_rate", "value": "8", "reason": "Marginal tariff slab"}
    second = send(client, created["id"], [rate]).json()
    assert len(second["overrides"][0]["from"].split(".")[-1]) <= 4  # rounded for the record


def test_inbox_row_shows_the_accepted_size(client, lead, db_session):
    """Once a quote is accepted, the size that counts is the homeowner's choice, not the guess."""
    verify(client, lead)
    quote_id = send(client, lead).json()["id"]
    row = next(r for r in client.get("/api/staff/leads").json() if r["id"] == lead)
    assert row["accepted_kw"] is None
    sign_in(client, OWNER)
    client.post(f"/api/quotes/{quote_id}/accept", headers=CSRF, json={"selected_kw": "2"})
    sign_in(client, DESK)
    row = next(r for r in client.get("/api/staff/leads").json() if r["id"] == lead)
    assert row["accepted_kw"] == "2"
    assert client.get(f"/api/staff/leads/{lead}").json()["accepted_kw"] == "2"
