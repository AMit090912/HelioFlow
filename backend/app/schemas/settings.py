"""Validation for the `settings` table (ARCHITECTURE §3.7). One field per key, with sane ranges."""

from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator


def _exact_decimal(value: Any) -> Any:
    # JSON numbers may arrive as float; go through str so 0.9 stays exactly 0.9.
    return Decimal(str(value)) if isinstance(value, float) else value


ExactDecimal = Annotated[Decimal, BeforeValidator(_exact_decimal)]


class BusinessSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    generation_kwh_per_kw_year: ExactDecimal = Field(gt=0, le=3000)
    roof_sqft_per_kw: ExactDecimal = Field(gt=0, le=1000)
    min_monthly_bill_for_survey: ExactDecimal = Field(ge=0)
    capacity_options_kw: list[ExactDecimal] = Field(min_length=1)
    usable_generation_pct: ExactDecimal = Field(gt=0, le=1)
    default_fixed_charge_monthly: ExactDecimal = Field(ge=0)
    quote_option_offsets: list[int] = Field(min_length=1)

    @field_validator("capacity_options_kw")
    @classmethod
    def _ascending_positive(cls, values: list[Decimal]) -> list[Decimal]:
        if any(v <= 0 for v in values) or values != sorted(set(values)):
            raise ValueError("capacity options must be positive, unique and ascending")
        return values

    @field_validator("quote_option_offsets")
    @classmethod
    def _includes_recommended(cls, values: list[int]) -> list[int]:
        if 0 not in values:
            raise ValueError("offsets must include 0 (the recommended size)")
        return values


REQUIRED_KEYS = frozenset(BusinessSettings.model_fields)
