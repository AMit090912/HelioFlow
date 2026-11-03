import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.schemas.bills import ReadingOut, plain


class VerificationIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    roof_area_sqft: Decimal = Field(gt=0, le=100_000)
    via: Literal["survey", "call"]
    sanctioned_load_kw: Decimal | None = Field(default=None, gt=0, le=100)
    notes: str | None = Field(default=None, max_length=2000)


class ReasonIn(BaseModel):
    reason: str = Field(max_length=1000)


class StaffLeadRow(BaseModel):
    id: uuid.UUID
    code: str
    homeowner_name: str
    created_at: datetime
    status: str
    score: str | None
    score_reasons: list[dict[str, Any]]
    recommended_kw: Decimal | None
    recommendation_status: str | None
    next_action: str | None
    flags: list[str]

    @field_serializer("recommended_kw")
    def _plain(self, value: Decimal | None) -> str | None:
        return plain(value)


class HomeownerContact(BaseModel):
    full_name: str
    phone: str | None
    email: str | None
    preferred_locale: str


class LoadOut(BaseModel):
    value: Decimal | None
    source: Literal["staff", "bill"] | None

    @field_serializer("value")
    def _plain(self, value: Decimal | None) -> str | None:
        return plain(value)


class EventOut(BaseModel):
    id: uuid.UUID
    kind: str
    from_status: str | None
    to_status: str | None
    actor_name: str
    note: str | None
    created_at: datetime


class QuoteRef(BaseModel):
    id: uuid.UUID
    number: str
    status: str
    sent_at: datetime
    selected_kw: Decimal | None

    @field_serializer("selected_kw")
    def _plain(self, value: Decimal | None) -> str | None:
        return plain(value)


class StaffLeadDetail(StaffLeadRow):
    homeowner: HomeownerContact
    ownership: str
    property_type: str
    roof_type: str
    roof_area_sqft: Decimal
    declared_monthly_bill: Decimal
    pincode: str
    seed_note: str | None
    sizing_detail: dict[str, Any] | None
    verified_roof_area_sqft: Decimal | None
    roof_verified_via: str | None
    roof_verified_at: datetime | None
    survey_notes: str | None
    sanctioned_load: LoadOut
    current_reading: ReadingOut | None
    events: list[EventOut]
    quotes: list[QuoteRef]

    @field_serializer("roof_area_sqft", "declared_monthly_bill", "verified_roof_area_sqft")
    def _plain_more(self, value: Decimal | None) -> str | None:
        return plain(value)
