"""Deterministic sanity checks on what the AI read (§6.3), and the per-month figures a person is
asked to confirm. Flags inform the person confirming the values; they never change a value or
reject a bill on their own (except document-level "this isn't a usable bill" flags).

Indian bills are not always monthly: spot "bill-cum-notice" receipts (e.g. TSSPDCL) often cover
two or three months. A bill's units, amount and fixed charge are for ITS period, so they are
converted to an average month before anyone confirms them (A-30).
"""

import re
from dataclasses import dataclass
from datetime import date
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


def _billing_days(e: BillExtraction) -> int | None:
    """Printed day count, else the days between the two reading dates (spot bills often print
    only "Previous 22/04/24, Present 22/07/24")."""
    if e.billing_days.value is not None:
        return e.billing_days.value if e.billing_days.value > 0 else None
    try:
        start = date.fromisoformat(e.previous_reading_date.value or "")
        end = date.fromisoformat(e.present_reading_date.value or "")
    except ValueError:
        return None
    days = (end - start).days
    return days if 0 < days <= 400 else None


def _readings_disagree(from_meter: Decimal, printed: int) -> bool:
    return abs(from_meter - Decimal(printed)) > max(Decimal(1), from_meter * Decimal("0.01"))


def _period_bill(e: BillExtraction) -> tuple[Decimal | None, bool]:
    """This period's charges. When the amount read is only part of what is payable for the
    period (one of several monthly instalments), the period total is used instead.

    - Arrears read: total − arrears is the period's bill.
    - Arrears not read: only when the total is ≈ k × the amount (k = 2–4, within 5%) AND the
      bill covers ≈ k months — otherwise the difference could be arrears, so the bill stays.
    Returns (amount, replaced)."""
    bill, total, arrears = e.bill_amount.value, e.total_due.value, e.arrears.value
    if bill is None or total is None or bill <= 0:
        return bill, False
    if arrears is not None and arrears >= 0:
        period_total = total - arrears
        if period_total > 0 and bill < period_total * Decimal("0.67"):
            return period_total, True
        return bill, False
    ratio = total / bill
    k = int(ratio.to_integral_value(rounding=ROUND_HALF_UP))
    days = _billing_days(e)
    if 2 <= k <= 4 and abs(ratio - k) <= Decimal("0.05") * k and days is not None:
        if abs(Decimal(days) / MONTH_DAYS - k) <= Decimal("0.5"):
            return total, True
    return bill, False


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
    bill_adjusted: bool = False  # the amount read looked like one instalment/month (flagged)


# A long bill whose amount works out under ₹4/unit for ≥ 200 units/month is almost certainly one
# month's instalment, not the period total: Indian home tariffs at that use are well above it.
ONE_MONTH_RATE_FLOOR = Decimal("4")
ONE_MONTH_MIN_UNITS = Decimal("200")


def _bill_per_month(
    e: BillExtraction, days: int | None, units: Decimal | None
) -> tuple[Decimal | None, bool]:
    raw, replaced = _period_bill(e)
    bill = _per_month(raw, days)
    if replaced or raw is None or bill is None or not units or days is None:
        return bill, replaced
    long_bill = Decimal(days) / MONTH_DAYS >= Decimal("1.5")
    if long_bill and units >= ONE_MONTH_MIN_UNITS and bill / units < ONE_MONTH_RATE_FLOOR:
        if RATE_RANGE[0] * 2 <= raw / units <= RATE_RANGE[1]:
            return raw, True  # one month's amount: already per month
    return bill, False


def monthly_figures(e: BillExtraction) -> MonthlyFigures:
    """What the person is asked to confirm: average units, bill and fixed charge per month.

    Units: the mean of ≥ 3 months of printed history (A-25); else this bill's units (or the
    meter-reading difference when units aren't printed), scaled to a month when the bill covers
    a longer or shorter period (A-30).
    """
    days = _billing_days(e)
    fixed = _per_month(e.fixed_charge.value, days)

    # A month outside the plausible range is a misreading: it is flagged (sanity_flags) and left
    # out here, so one bad digit can't distort the suggestion. At most the latest 24 months count.
    lo, hi = UNITS_RANGE
    history = [m for m in (e.monthly_units.value or []) if lo <= m.units <= hi][-24:]
    if len(history) >= 3:
        mean = Decimal(sum(m.units for m in history)) / len(history)
        units = mean.quantize(CENT, rounding=ROUND_HALF_UP)
        bill, adjusted = _bill_per_month(e, days, units)
        return MonthlyFigures(units, "history_mean", bill, fixed, days, adjusted)

    period_units: Decimal | None = None
    method: str | None = None
    from_meter = _units_from_readings(e)
    printed = e.current_units.value
    if printed is not None and not (
        from_meter is not None and _readings_disagree(from_meter, printed)
    ):
        period_units, method = Decimal(printed), "current_month"
    elif from_meter is not None:
        # Two readings and a subtraction beat one misread total (the flag still asks to check).
        period_units, method = from_meter, "meter_readings"
    elif history:
        period_units, method = Decimal(history[-1].units), "current_month"
    if period_units is None:
        bill, adjusted = _bill_per_month(e, days, None)
        return MonthlyFigures(None, None, bill, fixed, days, adjusted)

    scaled = _per_month(period_units, days)
    if scaled != period_units and method == "current_month":
        method = "period_normalised"
    bill, adjusted = _bill_per_month(e, days, scaled)
    return MonthlyFigures(scaled, method, bill, fixed, days, adjusted)


def suggested_average_units(e: BillExtraction) -> tuple[Decimal | None, str | None]:
    figures = monthly_figures(e)
    return figures.avg_monthly_units, figures.method


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
    days = _billing_days(e)
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
    if from_meter is not None and units is not None and _readings_disagree(from_meter, units):
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
    # ₹ per unit from the figures the person will confirm (period total, best units estimate).
    if monthly.bill_amount is not None and monthly.avg_monthly_units:
        rate = monthly.bill_amount / monthly.avg_monthly_units
        if not RATE_RANGE[0] <= rate <= RATE_RANGE[1]:
            _add(flags, "bill_amount", "rate_unusual")
    arrears, total = e.arrears.value, e.total_due.value
    if bill is not None and arrears and arrears > 0 and total is not None and bill >= total:
        _add(flags, "bill_amount", "may_include_arrears")
    if monthly.bill_adjusted:
        _add(flags, "bill_amount", "bill_amount_partial")
    if monthly.bill_amount is not None and declared_bill:
        if abs(monthly.bill_amount - declared_bill) / declared_bill > DECLARED_TOLERANCE:
            _add(flags, "bill_amount", "differs_from_declared")

    if monthly.avg_monthly_units is None:
        _add(flags, "current_units", "missing")
    return flags
