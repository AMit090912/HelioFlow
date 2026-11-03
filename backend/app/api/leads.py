"""Homeowner leads: create (screen 1), list mine and view one (screen 3). ARCHITECTURE §2."""

import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_owned_or_404, require_roles
from app.core.errors import ApiError
from app.models import BillReading, Lead, User
from app.models.enums import Ownership, PropertyType, RoofType
from app.schemas.leads import CONSENT_VERSION, LeadIn, LeadMine
from app.services.quotes import current_quote

router = APIRouter(prefix="/leads", tags=["leads"])
homeowner = require_roles("homeowner")


def _latest_reading(db: Session, lead_id: uuid.UUID) -> BillReading | None:
    return db.execute(
        select(BillReading)
        .where(BillReading.lead_id == lead_id)
        .order_by(desc(BillReading.created_at))
        .limit(1)
    ).scalar_one_or_none()


def _new_code() -> str:
    return f"LD-{secrets.randbelow(900_000) + 100_000}"


@router.post("", status_code=201, response_model=LeadMine)
def create_lead(
    body: LeadIn, db: Session = Depends(get_db), user: User = Depends(homeowner)
) -> LeadMine:
    if not body.consent:
        raise ApiError(422, "CONSENT_REQUIRED", "Please agree to how we use your details.")
    for _ in range(5):  # random codes; retry on the rare clash with the unique constraint
        lead = Lead(
            code=_new_code(),
            homeowner_id=user.id,
            ownership=Ownership(body.ownership),
            property_type=PropertyType(body.property_type),
            roof_type=RoofType(body.roof_type),
            roof_area_sqft=body.roof_area_sqft,
            declared_monthly_bill=body.monthly_bill,
            pincode=body.pincode,
            consent_at=datetime.now(UTC),
            consent_version=CONSENT_VERSION,
        )
        db.add(lead)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        return LeadMine.of(lead, None)
    raise ApiError(500, "INTERNAL_ERROR", "Could not create the lead. Try again.")


@router.get("/mine", response_model=list[LeadMine])
def my_leads(db: Session = Depends(get_db), user: User = Depends(homeowner)) -> list[LeadMine]:
    leads = db.execute(
        select(Lead).where(Lead.homeowner_id == user.id).order_by(desc(Lead.created_at))
    ).scalars()
    return [
        LeadMine.of(lead, _latest_reading(db, lead.id), current_quote(db, lead.id))
        for lead in leads
    ]


@router.get("/{lead_id}", response_model=LeadMine)
def get_lead(
    lead_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(homeowner)
) -> LeadMine:
    lead = get_owned_or_404(db, Lead, lead_id, user)
    return LeadMine.of(lead, _latest_reading(db, lead.id), current_quote(db, lead.id))
