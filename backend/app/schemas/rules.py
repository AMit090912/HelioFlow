import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.schemas.bills import plain


class PriceRuleIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    min_kw: Decimal = Field(gt=0, le=100)
    max_kw: Decimal = Field(gt=0, le=100)
    price_per_kw: Decimal = Field(gt=0, le=10_000_000)
    gst_inclusive: bool
    effective_from: date
    effective_to: date | None = None
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _ranges(self) -> "PriceRuleIn":
        if self.min_kw > self.max_kw:
            raise ValueError("min_kw must not exceed max_kw")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be on or after effective_from")
        return self


class SlabIn(BaseModel):
    from_kw: Decimal = Field(ge=0, le=100)
    to_kw: Decimal = Field(gt=0, le=100)
    amount_per_kw: Decimal = Field(ge=0, le=10_000_000)


class SubsidyRuleIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scheme_code: str = Field(min_length=2, max_length=60, pattern=r"^[A-Z0-9_]+$")
    segment: Literal["residential"]
    slabs: list[SlabIn] = Field(min_length=1, max_length=20)
    cap_amount: Decimal = Field(ge=0, le=100_000_000)
    effective_from: date
    effective_to: date | None = None
    source_note: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def _slabs_contiguous(self) -> "SubsidyRuleIn":
        """Slabs start at 0 kW and each begins where the previous one ended (§3.6)."""
        expected = Decimal("0")
        for slab in self.slabs:
            if slab.from_kw != expected or slab.to_kw <= slab.from_kw:
                raise ValueError(
                    "slabs must start at 0 and be contiguous, each with to_kw > from_kw"
                )
            expected = slab.to_kw
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be on or after effective_from")
        return self


class CloseIn(BaseModel):
    effective_to: date | None  # null re-opens the rule (still checked for overlap)


class SettingIn(BaseModel):
    value: Any


class PriceRuleOut(BaseModel):
    id: uuid.UUID
    min_kw: Decimal
    max_kw: Decimal
    price_per_kw: Decimal
    gst_inclusive: bool
    effective_from: date
    effective_to: date | None
    note: str | None

    @field_serializer("min_kw", "max_kw", "price_per_kw")
    def _plain(self, value: Decimal) -> str | None:
        return plain(value)


class SubsidyRuleOut(BaseModel):
    id: uuid.UUID
    scheme_code: str
    segment: str
    slabs: list[dict[str, str]]
    cap_amount: Decimal
    effective_from: date
    effective_to: date | None
    source_note: str

    @field_serializer("cap_amount")
    def _plain(self, value: Decimal) -> str | None:
        return plain(value)
