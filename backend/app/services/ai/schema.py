"""The only shape an AI reply may take (§6.1). Anything else is an invalid response.

Every field is {value, confidence}; value is null when the bill doesn't show it. Types are checked,
so valid JSON like {"units": "three hundred"} fails and the chain moves to the next provider.
A provider writing `"field": null` instead of `{"value": null}` means the same thing and is
accepted (Gemini does this). Fields added in bill-v2 default to "not read", so readings stored
under bill-v1 still parse.
"""

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Read(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    confidence: float = Field(default=0.0, ge=0, le=1)


class TextRead(_Read):
    value: str | None = None


class DecimalRead(_Read):
    value: Decimal | None = None


class IntRead(_Read):
    value: int | None = None


class MonthUnits(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    month: str = Field(max_length=10)
    units: int


class MonthsRead(_Read):
    value: list[MonthUnits] | None = None


_READS = (
    "consumer_number",
    "tariff_category",
    "sanctioned_load_kw",
    "monthly_units",
    "current_units",
    "billing_days",
    "previous_reading",
    "present_reading",
    "meter_multiplier",
    "bill_amount",
    "arrears",
    "total_due",
    "fixed_charge",
)


class BillExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    is_electricity_bill: bool
    # False for bills issued outside India (e.g. a Philippine cooperative); None = not stated.
    is_indian_bill: bool | None = None
    legibility: Literal["good", "fair", "poor"]
    consumer_number: TextRead = TextRead()
    tariff_category: TextRead = TextRead()
    sanctioned_load_kw: DecimalRead = DecimalRead()
    monthly_units: MonthsRead = MonthsRead()
    current_units: IntRead = IntRead()  # units for THIS bill's period (may be > 1 month)
    billing_days: IntRead = IntRead()  # length of this bill's period in days
    previous_reading: DecimalRead = DecimalRead()
    present_reading: DecimalRead = DecimalRead()
    meter_multiplier: DecimalRead = DecimalRead()  # "MF"; units = (present − previous) × MF
    bill_amount: DecimalRead = DecimalRead()  # this period's charges, before arrears/adjustments
    arrears: DecimalRead = DecimalRead()
    total_due: DecimalRead = DecimalRead()  # payable incl. arrears: never used as the bill
    fixed_charge: DecimalRead = DecimalRead()  # fixed / customer charges for the period

    @model_validator(mode="before")
    @classmethod
    def _null_is_not_read(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: ({} if k in _READS and v is None else v) for k, v in data.items()}
        return data
