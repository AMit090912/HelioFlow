import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.models import BillReading


class ConfirmIn(BaseModel):
    """Values a person confirms or types in. Required: what scoring and sizing need (§7, §8)."""

    model_config = ConfigDict(extra="ignore")

    consumer_number: str | None = Field(default=None, max_length=30, pattern=r"^[0-9 \-]*$")
    tariff_category: str | None = Field(default=None, max_length=60)
    # Two decimals at most: the columns keep two, and scoring must use what is saved.
    sanctioned_load_kw: Decimal | None = Field(
        default=None, ge=Decimal("0.1"), le=100, decimal_places=2
    )
    monthly_units: list[Annotated[int, Field(ge=0, le=5000)]] | None = Field(
        default=None, max_length=24
    )
    avg_monthly_units: Decimal = Field(ge=0, le=5000, decimal_places=2)
    bill_amount: Decimal = Field(gt=0, le=1_000_000, decimal_places=2)
    fixed_charge_monthly: Decimal | None = Field(default=None, ge=0, le=100_000, decimal_places=2)


def plain(value: Decimal | None) -> str | None:
    """340.00 → "340", 3.50 → "3.5": the value as a person would write it (no DB scale)."""
    if value is None:
        return None
    return format(value.normalize(), "f")


class ConfirmedValues(BaseModel):
    consumer_number: str | None
    tariff_category: str | None
    sanctioned_load_kw: Decimal | None
    monthly_units: list[int] | None
    avg_monthly_units: Decimal | None
    bill_amount: Decimal | None
    fixed_charge_monthly: Decimal | None

    @field_serializer(
        "sanctioned_load_kw", "avg_monthly_units", "bill_amount", "fixed_charge_monthly"
    )
    def _plain(self, value: Decimal | None) -> str | None:
        return plain(value)


class ReadingOut(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    status: str
    kind: str
    source_path: str | None
    quality: dict[str, Any] | None
    ai: dict[str, Any] | None
    flags: dict[str, list[str]]
    suggested_avg_monthly_units: Decimal | None
    suggested_method: str | None
    # Per-month bill and fixed charge, and the period they came from (A-30). Pre-fill the form.
    suggested_bill_amount: Decimal | None = None
    suggested_fixed_charge: Decimal | None = None
    billing_days: int | None = None
    confirmed: ConfirmedValues | None
    edited_fields: list[str]
    provider: str | None
    model: str | None
    is_demo: bool
    attempts: list[dict[str, Any]]
    created_at: datetime

    @field_serializer(
        "suggested_avg_monthly_units", "suggested_bill_amount", "suggested_fixed_charge"
    )
    def _plain_suggestions(self, value: Decimal | None) -> str | None:
        return plain(value)

    @classmethod
    def of(cls, reading: BillReading, kind: str) -> "ReadingOut":
        flags = dict(reading.validation_flags or {})
        suggestion = flags.pop("_suggested", None) or {}
        confirmed = None
        if reading.confirmed_at is not None:
            confirmed = ConfirmedValues(
                consumer_number=reading.consumer_number,
                tariff_category=reading.tariff_category,
                sanctioned_load_kw=reading.sanctioned_load_kw,
                monthly_units=reading.monthly_units,
                avg_monthly_units=reading.avg_monthly_units,
                bill_amount=reading.bill_amount,
                fixed_charge_monthly=reading.fixed_charge_monthly,
            )
        return cls(
            id=reading.id,
            lead_id=reading.lead_id,
            status=reading.status.value,
            kind=kind,
            source_path=reading.source_path.value if reading.source_path else None,
            quality=reading.quality,
            ai=reading.ai_values,
            flags=flags,
            suggested_avg_monthly_units=suggestion.get("avg_monthly_units"),
            suggested_method=suggestion.get("method"),
            suggested_bill_amount=suggestion.get("bill_amount"),
            suggested_fixed_charge=suggestion.get("fixed_charge_monthly"),
            billing_days=suggestion.get("billing_days"),
            confirmed=confirmed,
            edited_fields=list(reading.edited_fields or []),
            provider=reading.provider,
            model=reading.model,
            is_demo=reading.provider == "demo",
            # Attempt summaries only: raw provider responses never leave the server.
            attempts=[
                {k: a.get(k) for k in ("provider", "model", "outcome", "error_code", "ms")}
                for a in reading.attempts or []
            ],
            created_at=reading.created_at,
        )
