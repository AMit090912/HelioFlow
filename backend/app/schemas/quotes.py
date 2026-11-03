import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.schemas.bills import plain

OverrideField = Literal["usable_generation_pct", "fixed_charge_monthly", "savings_rate"]


class OverrideIn(BaseModel):
    """A sales override (§10). Preview accepts it without a reason; sending requires one."""

    model_config = ConfigDict(extra="ignore")

    field: OverrideField
    # Bounded so a typo can't produce a 500 or a huge response: no field needs more than
    # ₹1,00,000 or four decimals (a rate like ₹8.9706 per unit, a share like 0.9).
    value: Decimal = Field(ge=0, le=100_000, decimal_places=4)
    reason: str | None = Field(default=None, max_length=500)


class QuoteRequest(BaseModel):
    overrides: list[OverrideIn] = Field(default_factory=list, max_length=3)


class AcceptIn(BaseModel):
    selected_kw: Decimal = Field(gt=0, le=100)


class LoadRef(BaseModel):
    value: str | None
    source: Literal["staff", "bill"] | None


class QuotePreviewOut(BaseModel):
    """Live builder numbers: the same shape as a sent quote's options (snapshot format)."""

    priced_on: date
    recommended_kw: str
    provisional_kw: str | None
    max_allowed_kw: str
    removed: list[dict[str, str]]
    options: list[dict[str, Any]]
    sanctioned_load: LoadRef
    verified_roof_sqft: str | None
    overrides: list[dict[str, Any]]


class QuoteView(BaseModel):
    """A sent quote, built only from its immutable snapshot plus lifecycle columns."""

    id: uuid.UUID
    number: str
    status: str
    lead_id: uuid.UUID
    lead_code: str
    lead_status: str  # a closed lead's open quote can't be accepted (§2)
    sent_at: datetime
    priced_on: date
    selected_kw: Decimal | None
    accepted_at: datetime | None
    superseded_by_quote_id: uuid.UUID | None
    recommended_kw: str
    options: list[dict[str, Any]]
    removed: list[dict[str, str]]
    assumptions: list[str]
    overrides: list[dict[str, Any]]
    subsidy_rule: dict[str, Any] | None
    inputs: dict[str, Any]

    @field_serializer("selected_kw")
    def _plain(self, value: Decimal | None) -> str | None:
        return plain(value)
