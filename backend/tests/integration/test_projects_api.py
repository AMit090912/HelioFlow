"""Projects: advance → stages → events, simulated notifications, public status link (§12, §13)."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.models import Lead, Notification
from tests.integration.test_bills_api import CSRF, sign_in
from tests.integration.test_leads_api import signup
from tests.integration.test_quotes_api import (  # noqa: F401  (fixtures)
    DESK,
    OWNER,
    ai,
    lead,
    send,
    verify,
)

STAGES = [
    "advance_received",
    "installation_scheduled",
    "installation_completed",
    "net_metering_completed",
    "subsidy_applied",
    "subsidy_credited",
]


@pytest.fixture
def accepted(client, lead):  # noqa: F811
    """A lead whose 3 kW quote (net ₹1,02,000) the homeowner accepted; staff signed in."""
    verify(client, lead)
    quote_id = send(client, lead).json()["id"]
    sign_in(client, OWNER)
    res = client.post(f"/api/quotes/{quote_id}/accept", headers=CSRF, json={"selected_kw": "3"})
    assert res.status_code == 200
    sign_in(client, DESK)
    return lead


def advance(client, lead_id, amount="25000"):
    return client.post(f"/api/staff/leads/{lead_id}/advance", headers=CSRF, json={"amount": amount})


def move(client, project_id, to, **extra):
    return client.post(
        f"/api/staff/projects/{project_id}/stage", headers=CSRF, json={"to": to, **extra}
    )


@pytest.fixture
def project(client, accepted):
    body = advance(client, accepted).json()
    return body["project"]["id"], body["status_token"]


# --- Advance ---


def test_record_advance_creates_project_and_link(client, accepted, db_session):
    res = advance(client, accepted)
    assert res.status_code == 201, res.text
    body = res.json()
    token, proj = body["status_token"], body["project"]
    assert len(token) >= 40
    assert proj["stage"] == "advance_received" and proj["advance_amount"] == "25000"
    assert proj["advance_reference"].startswith("SIMULATED-")
    assert proj["link"]["active"] is True
    assert [e["to_stage"] for e in proj["events"]] == ["advance_received"]
    assert db_session.get(Lead, accepted).status.value == "converted"
    [note] = [n for n in proj["notifications"] if n["type"] == "status_link"]
    assert token not in note["message"] and "/s/" in note["message"]
    assert note["delivery_status"] == "simulated"
    stored = db_session.execute(select(Notification.message)).scalars().all()
    assert all(token not in m for m in stored)
    assert advance(client, accepted).status_code == 409  # one project per lead


def test_advance_only_on_accepted_lead(client, lead):  # noqa: F811
    verify(client, lead)
    send(client, lead)  # quoted, not accepted
    res = advance(client, lead)
    assert (res.status_code, res.json()["error"]["code"]) == (409, "LEAD_STATUS_CONFLICT")


def test_advance_cannot_exceed_net(client, accepted):
    res = advance(client, accepted, amount="102001")
    assert (res.status_code, res.json()["error"]["code"]) == (422, "ADVANCE_TOO_LARGE")
    assert advance(client, accepted, amount="0").status_code == 422
    assert advance(client, accepted, amount="102000").status_code == 201


# --- Stages ---


def test_stage_move_is_one_step_and_locked(client, project):
    pid, _ = project
    skip = move(client, pid, "installation_completed")
    assert (skip.status_code, skip.json()["error"]["code"]) == (409, "STAGE_NOT_NEXT")
    ok = move(client, pid, "installation_scheduled")
    assert ok.status_code == 200 and ok.json()["stage"] == "installation_scheduled"
    again = move(client, pid, "installation_scheduled")
    assert (again.status_code, again.json()["error"]["code"]) == (409, "STAGE_NOT_NEXT")
    for stage in STAGES[2:]:
        assert move(client, pid, stage).status_code == 200
    assert move(client, pid, "subsidy_credited").status_code == 409  # terminal


def test_backward_needs_reason(client, project):
    pid, _ = project
    move(client, pid, "installation_scheduled")
    bare = move(client, pid, "advance_received")
    assert (bare.status_code, bare.json()["error"]["code"]) == (422, "REASON_REQUIRED")
    ok = move(client, pid, "advance_received", note="Installer cancelled; rebooking")
    assert ok.status_code == 200 and ok.json()["stage"] == "advance_received"
    assert ok.json()["events"][0]["note"] == "Installer cancelled; rebooking"


def test_schedule_date_on_stage_two(client, project):
    pid, _ = project
    past = move(
        client, pid, "installation_scheduled", scheduled_for=str(date.today() - timedelta(1))
    )
    assert past.status_code == 422
    when = str(date.today() + timedelta(days=5))
    ok = move(client, pid, "installation_scheduled", scheduled_for=when)
    assert ok.status_code == 200 and ok.json()["scheduled_for"] == when


def test_stage_change_notifies_in_homeowner_language(client, project, db_session):
    sign_in(client, OWNER)
    client.patch("/api/auth/me", headers=CSRF, json={"preferred_locale": "mr"})
    sign_in(client, DESK)
    pid, _ = project
    detail = move(client, pid, "installation_scheduled").json()
    [note] = [n for n in detail["notifications"] if n["type"] == "stage_changed"]
    assert note["locale"] == "mr" and "इन्स्टॉलेशन" in note["message"]


def test_projects_list_shows_days_in_stage(client, project):
    rows = client.get("/api/staff/projects").json()
    assert rows[0]["stage"] == "advance_received" and rows[0]["days_in_stage"] == 0
    assert rows[0]["selected_kw"] == "3" and rows[0]["code"].startswith("LD-")


def test_homeowner_cannot_use_project_api(client, project):
    pid, _ = project
    sign_in(client, OWNER)
    assert client.get("/api/staff/projects").status_code == 403
    assert move(client, pid, "installation_scheduled").status_code == 403


# --- Public status link ---


def test_public_status_shows_stages(client, project):
    pid, token = project
    when = str(date.today() + timedelta(days=3))
    move(client, pid, "installation_scheduled", scheduled_for=when)
    client.cookies.clear()  # anyone with the link, signed out
    res = client.get(f"/api/public/status/{token}")
    assert res.status_code == 200
    assert res.headers["referrer-policy"] == "no-referrer"
    assert "noindex" in res.headers["x-robots-tag"]
    body = res.json()
    assert body["current_stage"] == "installation_scheduled"
    assert [s["stage"] for s in body["stages"]] == STAGES
    assert body["stages"][0]["done_at"] and body["stages"][2]["done_at"] is None
    assert body["scheduled_for"] == when


def test_public_status_has_no_personal_data(client, project):
    _, token = project
    client.cookies.clear()
    body = client.get(f"/api/public/status/{token}").json()
    assert set(body) == {"first_name", "code", "current_stage", "stages", "scheduled_for"}
    assert body["first_name"] == "Test"  # "Test Homeowner" → first name only
    text = str(body)
    assert "example.com" not in text and "₹" not in text and "25000" not in text


def test_regenerate_revokes_old_token(client, project):
    pid, old = project
    res = client.post(f"/api/staff/projects/{pid}/link", headers=CSRF)
    new = res.json()["status_token"]
    assert new != old
    client.cookies.clear()
    gone = client.get(f"/api/public/status/{old}")
    assert (gone.status_code, gone.json()["error"]["code"]) == (404, "LINK_INACTIVE")
    assert client.get(f"/api/public/status/{new}").status_code == 200


def test_revoked_link_is_inactive(client, project):
    pid, token = project
    assert client.delete(f"/api/staff/projects/{pid}/link", headers=CSRF).status_code == 204
    detail = client.get(f"/api/staff/projects/{pid}").json()
    assert detail["link"]["active"] is False
    client.cookies.clear()
    assert client.get(f"/api/public/status/{token}").status_code == 404
    assert client.get("/api/public/status/not-a-real-token").status_code == 404


def test_status_rate_limited(client, project):
    _, token = project
    client.cookies.clear()
    codes = [client.get(f"/api/public/status/{token}").status_code for _ in range(31)]
    assert codes[:30] == [200] * 30 and codes[30] == 429


def test_lead_mine_shows_project(client, project):
    sign_in(client, OWNER)
    mine = client.get("/api/leads/mine").json()[0]
    assert mine["status"] == "converted"
    assert mine["project"]["stage"] == "advance_received"
    assert len(mine["project"]["stages"]) == 6


def test_stranger_signed_in_sees_same_public_page(client, project):
    _, token = project
    signup(client, "neighbour@example.com")
    assert client.get(f"/api/public/status/{token}").status_code == 200


# --- Review fixes ---


def test_correction_back_to_scheduled_keeps_the_date(client, project):
    pid, token = project
    when = str(date.today() + timedelta(days=4))
    move(client, pid, "installation_scheduled", scheduled_for=when)
    first_done = move(client, pid, "installation_completed").json()
    scheduled_at = first_done["stages"][1]["done_at"]
    back = move(client, pid, "installation_scheduled", note="Panels failed inspection")
    assert back.status_code == 200
    assert back.json()["scheduled_for"] == when
    assert back.json()["stages"][1]["done_at"] == scheduled_at  # not restamped by the correction
    assert back.json()["stages"][2]["done_at"] is None
    client.cookies.clear()
    assert client.get(f"/api/public/status/{token}").json()["scheduled_for"] == when


def test_link_changes_are_logged_with_who(client, project, db_session):
    from app.models import LeadEvent, Project

    pid, _ = project
    client.post(f"/api/staff/projects/{pid}/link", headers=CSRF)
    client.delete(f"/api/staff/projects/{pid}/link", headers=CSRF)
    lead_id = db_session.get(Project, pid).lead_id
    kinds = [
        e.kind
        for e in db_session.execute(
            select(LeadEvent).where(LeadEvent.lead_id == lead_id).order_by(LeadEvent.created_at)
        ).scalars()
    ]
    assert kinds[-2:] == ["link_regenerated", "link_revoked"]


def test_tokens_are_redacted_from_access_logs():
    import logging

    from app.core.logging import RedactSecretPaths

    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '%s - "%s %s HTTP/%s" %d',
        ("1.2.3.4", "GET", "/api/public/status/AbC-123_xyz?x=1", "1.1", 200),
        None,
    )
    RedactSecretPaths().filter(record)
    assert "AbC-123_xyz" not in record.getMessage() and "/status/****" in record.getMessage()


@pytest.mark.parametrize("amount", ["0.001", "0.5", "25000.123"])
def test_advance_is_whole_paise_and_at_least_a_rupee(client, accepted, amount):
    """The column holds paise; anything finer would be silently rounded (₹0.001 became ₹0)."""
    res = advance(client, accepted, amount)
    assert res.status_code == 422, res.text


def test_installation_date_is_within_two_years(client, project):
    pid, _ = project
    far = move(client, pid, "installation_scheduled", scheduled_for="9999-12-31")
    assert (far.status_code, far.json()["error"]["code"]) == (422, "DATE_TOO_FAR")


def test_revoking_twice_logs_once(client, project, db_session):
    from sqlalchemy import func, select

    from app.models import LeadEvent

    pid, _ = project
    for _ in range(2):
        assert client.delete(f"/api/staff/projects/{pid}/link", headers=CSRF).status_code == 204
    count = db_session.scalar(
        select(func.count()).select_from(LeadEvent).where(LeadEvent.kind == "link_revoked")
    )
    assert count == 1
