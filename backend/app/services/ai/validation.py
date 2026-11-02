"""Deterministic sanity checks on what the AI read (§6.3). Flags inform the person confirming the
values; they never change a value or reject a bill on their own."""

import re
from decimal import ROUND_HALF_UP, Decimal

from app.services.ai.schema import BillExtraction

LOW_CONFIDENCE = 0.7
UNITS_RANGE = (0, 5000)
LOAD_RANGE = (Decimal("0.1"), Decimal("100"))
RATE_RANGE = (Decimal("2"), Decimal("25"))  # ₹/unit implied by bill ÷ units
DECLARED_TOLERANCE = Decimal("0.30")
_CONSUMER_NO = re.compile(r"^\d{9,15}$")  # A-18: soft check, the exact DISCOM format is unknown

FIELDS = (
    "consumer_number",
    "tariff_category",
    "sanctioned_load_kw",
    "monthly_units",
    "current_units",
    "bill_amount",
    "fixed_charge",
)


def _add(flags: dict[str, list[str]], field: str, code: str) -> None:
    flags.setdefault(field, [])
    if code not in flags[field]:
        flags[field].append(code)


def sanity_flags(e: BillExtraction, declared_bill: Decimal | None) -> dict[str, list[str]]:
    flags: dict[str, list[str]] = {}
    if not e.is_electricity_bill:
        _add(flags, "document", "not_electricity_bill")
    if e.legibility == "poor":
        _add(flags, "document", "legibility_poor")

    for name in FIELDS:
        read = getattr(e, name)
        if read.value is not None and read.confidence < LOW_CONFIDENCE:
            _add(flags, name, "low_confidence")

    lo, hi = UNITS_RANGE
    if e.current_units.value is not None and not lo <= e.current_units.value <= hi:
        _add(flags, "current_units", "out_of_range")
    if e.monthly_units.value and any(not lo <= m.units <= hi for m in e.monthly_units.value):
        _add(flags, "monthly_units", "out_of_range")

    load = e.sanctioned_load_kw.value
    if load is not None and not LOAD_RANGE[0] <= load <= LOAD_RANGE[1]:
        _add(flags, "sanctioned_load_kw", "out_of_range")

    number = e.consumer_number.value
    if number is not None and not _CONSUMER_NO.match(re.sub(r"[\s-]", "", number)):
        _add(flags, "consumer_number", "format_unusual")

    bill = e.bill_amount.value
    units = e.current_units.value
    if bill is not None and units:
        rate = bill / Decimal(units)
        if not RATE_RANGE[0] <= rate <= RATE_RANGE[1]:
            _add(flags, "bill_amount", "rate_unusual")
    if bill is not None and declared_bill:
        if abs(bill - declared_bill) / declared_bill > DECLARED_TOLERANCE:
            _add(flags, "bill_amount", "differs_from_declared")

    if e.current_units.value is None and not e.monthly_units.value:
        _add(flags, "current_units", "missing")
    return flags


def suggested_average_units(e: BillExtraction) -> tuple[Decimal | None, str | None]:
    """Mean of ≥ 3 months of history, else this bill's units (A-25)."""
    history = e.monthly_units.value or []
    if len(history) >= 3:
        mean = Decimal(sum(m.units for m in history)) / len(history)
        return mean.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "history_mean"
    if e.current_units.value is not None:
        return Decimal(e.current_units.value), "current_month"
    if history:
        return Decimal(history[-1].units), "current_month"
    return None, None
