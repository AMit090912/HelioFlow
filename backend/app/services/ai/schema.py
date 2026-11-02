"""The only shape an AI reply may take (§6.1). Anything else is an invalid response.

Every field is {value, confidence}; value is null when the bill doesn't show it. Types are checked,
so valid JSON like {"units": "three hundred"} fails and the chain moves to the next provider.
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class BillExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    is_electricity_bill: bool
    legibility: Literal["good", "fair", "poor"]
    consumer_number: TextRead = TextRead()
    tariff_category: TextRead = TextRead()
    sanctioned_load_kw: DecimalRead = DecimalRead()
    monthly_units: MonthsRead = MonthsRead()
    current_units: IntRead = IntRead()
    bill_amount: DecimalRead = DecimalRead()
    fixed_charge: DecimalRead = DecimalRead()
