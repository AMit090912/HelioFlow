"""What staff do to a lead after qualification (ARCHITECTURE §2 sales journey, §8).

Every action locks the lead row, checks the status machine (forward only), and writes a
`lead_events` row. Callers commit.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import BillReading, Lead, LeadEvent, User
from app.models.enums import LeadStatus, NextAction, RoofVerifiedVia

TERMINAL = {LeadStatus.accepted, LeadStatus.converted, LeadStatus.closed_lost}
# Verification can be (re)recorded until the homeowner accepts a quote.
VERIFIABLE = {
    LeadStatus.survey_pending,
    LeadStatus.call_pending,
    LeadStatus.surveyed,
    LeadStatus.quoted,
}
QUALIFIED = {LeadStatus.survey_pending, LeadStatus.call_pending}


def lock_lead(db: Session, lead_id) -> Lead:
    lead = db.get(Lead, lead_id, with_for_update=True, populate_existing=True)
    if lead is None:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    return lead


def log_event(
    db: Session,
    lead: Lead,
    actor: User,
    kind: str,
    *,
    to_status: LeadStatus | None = None,
    note: str | None = None,
) -> None:
    """Records the action and, when `to_status` is given, moves the lead there."""
    before = lead.status
    if to_status is not None:
        lead.status = to_status
    db.add(
        LeadEvent(
            lead_id=lead.id,
            kind=kind,
            from_status=before,
            to_status=lead.status,
            actor_id=actor.id,
            note=note,
        )
    )


def _conflict(lead: Lead) -> ApiError:
    return ApiError(
        409, "LEAD_STATUS_CONFLICT", f"Not possible while the lead is {lead.status.value}."
    )


def _reason(reason: str) -> str:
    cleaned = " ".join(reason.split())
    if len(cleaned) < 5:
        raise ApiError(422, "REASON_REQUIRED", "Give a short reason (at least 5 characters).")
    return cleaned


def record_verification(
    db: Session,
    lead: Lead,
    actor: User,
    *,
    roof_area_sqft: Decimal,
    via: RoofVerifiedVia,
    sanctioned_load_kw: Decimal | None,
    notes: str | None,
) -> Lead:
    if lead.status not in VERIFIABLE:
        raise _conflict(lead)
    now = datetime.now(UTC)
    lead.verified_roof_area_sqft = roof_area_sqft
    lead.roof_verified_via = via
    lead.roof_verified_by = actor.id
    lead.roof_verified_at = now
    if sanctioned_load_kw is not None:
        lead.verified_sanctioned_load_kw = sanctioned_load_kw
        lead.load_verified_by = actor.id
        lead.load_verified_at = now
    if notes is not None and notes.strip():
        lead.survey_notes = notes.strip()
    if via == RoofVerifiedVia.survey:
        lead.surveyed_at, lead.surveyed_by = now, actor.id
    # Qualified leads move on to "surveyed"; a lead already surveyed or quoted stays put.
    to = LeadStatus.surveyed if lead.status in QUALIFIED else None
    log_event(
        db,
        lead,
        actor,
        "verified",
        to_status=to,
        note=f"roof {roof_area_sqft} sq ft via {via.value}",
    )
    return lead


def upgrade_to_visit(db: Session, lead: Lead, actor: User, reason: str) -> Lead:
    note = _reason(reason)
    if lead.status != LeadStatus.call_pending:
        raise _conflict(lead)
    lead.next_action = NextAction.survey_visit
    log_event(db, lead, actor, "upgraded", to_status=LeadStatus.survey_pending, note=note)
    return lead


def close_lost(db: Session, lead: Lead, actor: User, reason: str) -> Lead:
    note = _reason(reason)
    if lead.status in TERMINAL:
        raise _conflict(lead)
    log_event(db, lead, actor, "closed", to_status=LeadStatus.closed_lost, note=note)
    return lead


def effective_sanctioned_load(
    db: Session, lead: Lead
) -> tuple[Decimal | None, Literal["staff", "bill"] | None]:
    """Staff's DISCOM-record value wins; otherwise the homeowner-confirmed bill value."""
    if lead.verified_sanctioned_load_kw is not None:
        return lead.verified_sanctioned_load_kw, "staff"
    if lead.current_bill_reading_id is not None:
        reading = db.get(BillReading, lead.current_bill_reading_id)
        if reading is not None and reading.sanctioned_load_kw is not None:
            return reading.sanctioned_load_kw, "bill"
    return None, None
