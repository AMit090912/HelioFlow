import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.models import BillReading, Lead, Quote
from app.schemas.bills import plain

CONSENT_VERSION = "2026-11-v1"


class LeadDetails(BaseModel):
    """Screen 1, step 1: the home details. Editable until the bill is confirmed."""

    model_config = ConfigDict(extra="ignore")

    ownership: Literal["owner", "tenant"]
    property_type: Literal["home", "business"]
    roof_type: Literal["rcc_flat", "metal_sheet", "tiled", "other"]
    roof_area_sqft: Decimal = Field(gt=0, le=100_000)
    monthly_bill: Decimal = Field(gt=0, le=1_000_000)
    pincode: str = Field(pattern=r"^[1-9][0-9]{5}$")


class LeadIn(LeadDetails):
    """Step 1 + the consent from step 2 (ARCHITECTURE §2, §14)."""

    consent: bool


class ReadingRef(BaseModel):
    id: uuid.UUID
    status: str


class QuoteRef(BaseModel):
    id: uuid.UUID
    status: str


class LeadMine(BaseModel):
    """What a homeowner sees about their own lead. The score and its reasons are staff-only:
    a homeowner is never shown "Low" (§2), only their next step."""

    id: uuid.UUID
    code: str
    status: str
    ownership: str
    property_type: str
    roof_type: str
    roof_area_sqft: Decimal
    declared_monthly_bill: Decimal
    pincode: str
    next_action: str | None
    recommended_kw: Decimal | None
    recommendation_status: Literal["provisional", "final"] | None
    current_reading: ReadingRef | None
    latest_reading: ReadingRef | None
    current_quote: QuoteRef | None = None
    project: dict[str, Any] | None = None  # {stage, stages[{stage, done_at}], scheduled_for}
    created_at: datetime

    @field_serializer("roof_area_sqft", "declared_monthly_bill", "recommended_kw")
    def _plain(self, value: Decimal | None) -> str | None:
        return plain(value)

    @classmethod
    def of(cls, lead: Lead, latest: BillReading | None, quote: Quote | None = None) -> "LeadMine":
        detail = lead.sizing_detail or {}
        current = None
        if lead.current_bill_reading_id is not None:
            current = ReadingRef(id=lead.current_bill_reading_id, status="confirmed")
        return cls(
            id=lead.id,
            code=lead.code,
            status=lead.status.value,
            ownership=lead.ownership.value,
            property_type=lead.property_type.value,
            roof_type=lead.roof_type.value,
            roof_area_sqft=lead.roof_area_sqft,
            declared_monthly_bill=lead.declared_monthly_bill,
            pincode=lead.pincode,
            next_action=lead.next_action.value if lead.next_action else None,
            recommended_kw=lead.recommended_kw,
            recommendation_status=detail.get("status") if lead.next_action else None,
            current_reading=current,
            latest_reading=None
            if latest is None
            else ReadingRef(id=latest.id, status=latest.status.value),
            current_quote=None
            if quote is None
            else QuoteRef(id=quote.id, status=quote.status.value),
            created_at=lead.created_at,
        )
