"""Staff screens 6–7: leads inbox, lead detail and the actions on a lead (§2, §4)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_roles
from app.core.errors import ApiError
from app.models import BillFile, BillReading, Lead, LeadEvent, Quote, User
from app.models.enums import LeadScore, LeadStatus, RoofVerifiedVia
from app.schemas.bills import ReadingOut
from app.schemas.quotes import LoadRef, QuotePreviewOut, QuoteRequest, QuoteView
from app.schemas.staff import (
    EventOut,
    HomeownerContact,
    LoadOut,
    QuoteRef,
    ReasonIn,
    StaffLeadDetail,
    StaffLeadRow,
    VerificationIn,
)
from app.services import lead_actions, quotes

router = APIRouter(prefix="/staff", tags=["staff"])
staff_only = require_roles("sales", "admin")
# The default inbox is the work queue: not drafts still being filled in, not closed leads.
HIDDEN_BY_DEFAULT = (LeadStatus.draft, LeadStatus.closed_lost)


def _row_fields(lead: Lead, homeowner_name: str) -> dict:
    detail = lead.sizing_detail or {}
    flags = list(detail.get("flags", []))
    # Qualification-time flags that staff have since resolved are not shown again.
    if lead.verified_roof_area_sqft is not None:
        flags = [f for f in flags if f not in ("roof_unverified", "roof_too_small")]
    if lead.verified_sanctioned_load_kw is not None:
        flags = [f for f in flags if f != "sanctioned_load_unknown"]
    if lead.current_bill_reading_id is None:
        flags.append("bill_unverified")
    return {
        "id": lead.id,
        "code": lead.code,
        "homeowner_name": homeowner_name,
        "created_at": lead.created_at,
        "status": lead.status.value,
        "score": lead.score.value if lead.score else None,
        "score_reasons": lead.score_reasons or [],
        "recommended_kw": lead.recommended_kw,
        "recommendation_status": detail.get("status") if lead.next_action else None,
        "next_action": lead.next_action.value if lead.next_action else None,
        "flags": flags,
    }


@router.get("/leads", response_model=list[StaffLeadRow])
def inbox(
    score: LeadScore | None = Query(default=None),
    status: LeadStatus | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(staff_only),
) -> list[StaffLeadRow]:
    query = select(Lead, User.full_name).join(User, User.id == Lead.homeowner_id)
    if score is not None:
        query = query.where(Lead.score == score)
    if status is not None:
        query = query.where(Lead.status == status)
    else:
        query = query.where(Lead.status.not_in(HIDDEN_BY_DEFAULT))
    rank = case((Lead.score == LeadScore.high, 0), (Lead.score == LeadScore.low, 1), else_=2)
    query = query.order_by(rank, Lead.created_at.desc()).limit(500)
    return [StaffLeadRow(**_row_fields(lead, name)) for lead, name in db.execute(query)]


def _detail(db: Session, lead: Lead) -> StaffLeadDetail:
    owner = db.get(User, lead.homeowner_id)
    reading = None
    if lead.current_bill_reading_id is not None:
        row = db.get(BillReading, lead.current_bill_reading_id)
        kind = db.get(BillFile, row.bill_file_id).kind.value
        reading = ReadingOut.of(row, kind=kind)
    load, source = lead_actions.effective_sanctioned_load(db, lead)
    events = db.execute(
        select(LeadEvent, User.full_name)
        .join(User, User.id == LeadEvent.actor_id)
        .where(LeadEvent.lead_id == lead.id)
        .order_by(LeadEvent.created_at.desc())
    ).all()
    quotes = db.execute(
        select(Quote).where(Quote.lead_id == lead.id).order_by(Quote.sent_at.desc())
    ).scalars()
    return StaffLeadDetail(
        **_row_fields(lead, owner.full_name),
        homeowner=HomeownerContact(
            full_name=owner.full_name,
            phone=owner.phone,
            email=owner.email,
            preferred_locale=owner.preferred_locale.value,
        ),
        ownership=lead.ownership.value,
        property_type=lead.property_type.value,
        roof_type=lead.roof_type.value,
        roof_area_sqft=lead.roof_area_sqft,
        declared_monthly_bill=lead.declared_monthly_bill,
        pincode=lead.pincode,
        seed_note=lead.seed_note,
        sizing_detail=lead.sizing_detail,
        verified_roof_area_sqft=lead.verified_roof_area_sqft,
        roof_verified_via=lead.roof_verified_via.value if lead.roof_verified_via else None,
        roof_verified_at=lead.roof_verified_at,
        survey_notes=lead.survey_notes,
        sanctioned_load=LoadOut(value=load, source=source),
        current_reading=reading,
        events=[
            EventOut(
                id=e.id,
                kind=e.kind,
                from_status=e.from_status.value if e.from_status else None,
                to_status=e.to_status.value if e.to_status else None,
                actor_name=name,
                note=e.note,
                created_at=e.created_at,
            )
            for e, name in events
        ],
        quotes=[
            QuoteRef(
                id=q.id,
                number=q.number,
                status=q.status.value,
                sent_at=q.sent_at,
                selected_kw=q.selected_kw,
            )
            for q in quotes
        ],
    )


def _lead_or_404(db: Session, lead_id: uuid.UUID) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    return lead


@router.get("/leads/{lead_id}", response_model=StaffLeadDetail)
def lead_detail(
    lead_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(staff_only)
) -> StaffLeadDetail:
    return _detail(db, _lead_or_404(db, lead_id))


@router.post("/leads/{lead_id}/verification", response_model=StaffLeadDetail)
def verify(
    lead_id: uuid.UUID,
    body: VerificationIn,
    db: Session = Depends(get_db),
    user: User = Depends(staff_only),
) -> StaffLeadDetail:
    lead = lead_actions.lock_lead(db, lead_id)
    lead_actions.record_verification(
        db,
        lead,
        user,
        roof_area_sqft=body.roof_area_sqft,
        via=RoofVerifiedVia(body.via),
        sanctioned_load_kw=body.sanctioned_load_kw,
        notes=body.notes,
    )
    db.commit()
    return _detail(db, lead)


@router.post("/leads/{lead_id}/upgrade", response_model=StaffLeadDetail)
def upgrade(
    lead_id: uuid.UUID,
    body: ReasonIn,
    db: Session = Depends(get_db),
    user: User = Depends(staff_only),
) -> StaffLeadDetail:
    lead = lead_actions.lock_lead(db, lead_id)
    lead_actions.upgrade_to_visit(db, lead, user, body.reason)
    db.commit()
    return _detail(db, lead)


@router.post("/leads/{lead_id}/close", response_model=StaffLeadDetail)
def close(
    lead_id: uuid.UUID,
    body: ReasonIn,
    db: Session = Depends(get_db),
    user: User = Depends(staff_only),
) -> StaffLeadDetail:
    lead = lead_actions.lock_lead(db, lead_id)
    lead_actions.close_lost(db, lead, user, body.reason)
    db.commit()
    return _detail(db, lead)


@router.post("/leads/{lead_id}/quote-preview", response_model=QuotePreviewOut)
def quote_preview(
    lead_id: uuid.UUID,
    body: QuoteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(staff_only),
) -> QuotePreviewOut:
    """Live builder numbers. Nothing is stored; overrides don't need reasons yet."""
    lead = _lead_or_404(db, lead_id)
    on = quotes.today_in_india()
    result, _, load_source = quotes.preview(db, lead, body.overrides, on)
    return QuotePreviewOut(
        priced_on=on,
        provisional_kw=quotes.s(lead.recommended_kw),
        sanctioned_load=LoadRef(
            value=quotes.s(result.inputs.sanctioned_load_kw), source=load_source
        ),
        verified_roof_sqft=quotes.s(lead.verified_roof_area_sqft),
        overrides=quotes.overrides_record(result, body.overrides, None),
        **quotes.options_payload(result),
    )


@router.post("/leads/{lead_id}/quotes", response_model=QuoteView, status_code=201)
def send_quote(
    lead_id: uuid.UUID,
    body: QuoteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(staff_only),
) -> QuoteView:
    _lead_or_404(db, lead_id)
    quote = quotes.send_quote(db, lead_id, user, body.overrides)
    db.commit()
    return quotes.view_of(quote, db.get(Lead, lead_id))
