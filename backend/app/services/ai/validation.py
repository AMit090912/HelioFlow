"""Deterministic sanity checks on what the AI read (§6.3), and the per-month figures a person is
asked to confirm. Flags inform the person confirming the values; they never change a value or
reject a bill on their own (except document-level "this isn't a usable bill" flags).

Indian bills are not always monthly: spot "bill-cum-notice" receipts (e.g. TSSPDCL) often cover
two or three months. A bill's units, amount and fixed charge are for ITS period, so they are
converted to an average month before anyone confirms them (A-30).
"""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.services.ai.schema import BillExtraction

LOW_CONFIDENCE = 0.7
UNITS_RANGE = (0, 5000)
LOAD_RANGE = (Decimal("0.1"), Decimal("100"))
RATE_RANGE = (Decimal("2"), Decimal("25"))  # ₹/unit implied by bill ÷ units
DECLARED_TOLERANCE = Decimal("0.30")
_CONSUMER_NO = re.compile(r"^\d{9,15}$")  # A-18: soft check, the exact DISCOM format is unknown
_ONE_DIGIT_REPEATED = re.compile(r"^(\d)\1+$")  # 000000000000: a masked number read as digits

# A-30: a bill covering 25–35 days counts as one month as printed; anything else is scaled to
# an average month of 365/12 days.
MONTH_DAYS = Decimal(365) / Decimal(12)
ONE_MONTH_DAYS = (25, 35)
CENT = Decimal("0.01")

FIELDS = (
    "consumer_number",
    "tariff_category",
    "sanctioned_load_kw",
    "monthly_units",
    "current_units",
    "billing_days",
    "bill_amount",
    "fixed_charge",
)


def _add(flags: dict[str, list[str]], field: str, code: str) -> None:
    flags.setdefault(field, [])
    if code not in flags[field]:
        flags[field].append(code)


def _units_from_readings(e: BillExtraction) -> Decimal | None:
    previous, present = e.previous_reading.value, e.present_reading.value
    if previous is None or present is None or present < previous:  # unknown, or meter rollover
        return None
    return (present - previous) * (e.meter_multiplier.value or Decimal(1))


def _per_month(value: Decimal | None, days: int | None) -> Decimal | None:
    if value is None:
        return None
    if days is None or ONE_MONTH_DAYS[0] <= days <= ONE_MONTH_DAYS[1]:
        return value.normalize() if value == value.to_integral() else value
    return (value * MONTH_DAYS / Decimal(days)).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class MonthlyFigures:
    avg_monthly_units: Decimal | None
    method: str | None  # history_mean | period_normalised | current_month | meter_readings
    bill_amount: Decimal | None  # this period's charges, per month
    fixed_charge: Decimal | None  # per month
    billing_days: int | None


def monthly_figures(e: BillExtraction) -> MonthlyFigures:
    """What the person is asked to confirm: average units, bill and fixed charge per month.

    Units: the mean of ≥ 3 months of printed history (A-25); else this bill's units (or the
    meter-reading difference when units aren't printed), scaled to a month when the bill covers
    a longer or shorter period (A-30).
    """
    days = e.billing_days.value
    if days is not None and days <= 0:
        days = None
    bill = _per_month(e.bill_amount.value, days)
    fixed = _per_month(e.fixed_charge.value, days)

    history = e.monthly_units.value or []
    if len(history) >= 3:
        mean = Decimal(sum(m.units for m in history)) / len(history)
        units = mean.quantize(CENT, rounding=ROUND_HALF_UP)
        return MonthlyFigures(units, "history_mean", bill, fixed, days)

    period_units: Decimal | None = None
    method: str | None = None
    if e.current_units.value is not None:
        period_units, method = Decimal(e.current_units.value), "current_month"
    elif (from_meter := _units_from_readings(e)) is not None:
        period_units, method = from_meter, "meter_readings"
    elif history:
        period_units, method = Decimal(history[-1].units), "current_month"
    if period_units is None:
        return MonthlyFigures(None, None, bill, fixed, days)

    scaled = _per_month(period_units, days)
    if scaled != period_units and method == "current_month":
        method = "period_normalised"
    return MonthlyFigures(scaled, method, bill, fixed, days)


def suggested_average_units(e: BillExtraction) -> tuple[Decimal | None, str | None]:
    figures = monthly_figures(e)
    return figures.avg_monthly_units, figures.method


def sanity_flags(e: BillExtraction, declared_bill: Decimal | None) -> dict[str, list[str]]:
    flags: dict[str, list[str]] = {}
    if not e.is_electricity_bill:
        _add(flags, "document", "not_electricity_bill")
    if e.is_indian_bill is False:
        _add(flags, "document", "not_indian_bill")
    if e.legibility == "poor":
        _add(flags, "document", "legibility_poor")

    for name in FIELDS:
        read = getattr(e, name)
        if read.value is not None and read.confidence < LOW_CONFIDENCE:
            _add(flags, name, "low_confidence")

    lo, hi = UNITS_RANGE
    days = e.billing_days.value
    monthly = monthly_figures(e)
    # Range checks apply per month: a 3-month bill may legitimately show 1,700 units.
    this_bill = _per_month(
        Decimal(e.current_units.value) if e.current_units.value is not None else None, days
    )
    if this_bill is not None and not lo <= this_bill <= hi:
        _add(flags, "current_units", "out_of_range")
    if e.monthly_units.value and any(not lo <= m.units <= hi for m in e.monthly_units.value):
        _add(flags, "monthly_units", "out_of_range")
    if days is not None and not ONE_MONTH_DAYS[0] <= days <= ONE_MONTH_DAYS[1]:
        _add(flags, "current_units", "long_billing_period")

    from_meter = _units_from_readings(e)
    units = e.current_units.value
    if from_meter is not None and units is not None:
        if abs(from_meter - Decimal(units)) > max(Decimal(1), from_meter * Decimal("0.01")):
            _add(flags, "current_units", "units_mismatch_readings")

    load = e.sanctioned_load_kw.value
    if load is not None and not LOAD_RANGE[0] <= load <= LOAD_RANGE[1]:
        _add(flags, "sanctioned_load_kw", "out_of_range")

    number = e.consumer_number.value
    if number is not None:
        digits = re.sub(r"[\s-]", "", number)
        if not _CONSUMER_NO.match(digits) or _ONE_DIGIT_REPEATED.match(digits):
            _add(flags, "consumer_number", "format_unusual")

    bill = e.bill_amount.value
    if bill is not None and units:
        rate = bill / Decimal(units)  # both are for the same period, so no scaling needed
        if not RATE_RANGE[0] <= rate <= RATE_RANGE[1]:
            _add(flags, "bill_amount", "rate_unusual")
    arrears, total = e.arrears.value, e.total_due.value
    if bill is not None and arrears and arrears > 0 and total is not None and bill >= total:
        _add(flags, "bill_amount", "may_include_arrears")
    if monthly.bill_amount is not None and declared_bill:
        if abs(monthly.bill_amount - declared_bill) / declared_bill > DECLARED_TOLERANCE:
            _add(flags, "bill_amount", "differs_from_declared")

    if monthly.avg_monthly_units is None:
        _add(flags, "current_units", "missing")
    return flags
