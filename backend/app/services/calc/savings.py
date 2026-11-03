"""Savings and payback estimates (ARCHITECTURE §10). Always labelled estimates, never guaranteed.

Savings count only generation the home itself uses (surplus exports valued at ₹0, A-7) at the
variable part of its own tariff (bill minus fixed charge, A-8), so an estimate can never exceed
the variable part of today's bill. Missing inputs give "not available", never a made-up number.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.services.calc.errors import CalcError
from app.services.calc.rounding import one_decimal, rupees, whole
from app.services.calc.types import Settings

ZERO = Decimal("0")


@dataclass(frozen=True)
class Overrides:
    """Sales-staff overrides, recorded in the quote snapshot (§10)."""

    usable_generation_pct: Decimal | None = None
    fixed_charge_monthly: Decimal | None = None
    savings_rate: Decimal | None = None


@dataclass(frozen=True)
class Savings:
    annual_generation: int  # kWh/yr
    usable_generation: Decimal  # kWh/yr, exact
    usable_generation_pct: Decimal
    fixed_charge: Decimal
    fixed_charge_source: Literal["override", "bill", "default"]
    savings_rate: Decimal | None  # ₹/kWh, exact
    annual_savings: Decimal | None  # ₹, rounded
    status: Literal["ok", "not_available"]
    reason: str | None


@dataclass(frozen=True)
class Payback:
    years: Decimal | None
    status: Literal["ok", "immediate", "not_available"]


def validate_overrides(overrides: Overrides) -> None:
    """An override is applied exactly as given or rejected — never silently replaced (§10)."""
    pct, fixed, rate = (
        overrides.usable_generation_pct,
        overrides.fixed_charge_monthly,
        overrides.savings_rate,
    )
    problems = []
    if pct is not None and not (0 < pct <= 1):
        problems.append("usable_generation_pct")
    if fixed is not None and fixed < 0:
        problems.append("fixed_charge_monthly")
    if rate is not None and rate <= 0:
        problems.append("savings_rate")
    if problems:
        raise CalcError("INVALID_INPUT", "Some overrides are out of range.", fields=problems)


def estimate_savings(
    *,
    kw: Decimal,
    avg_monthly_units: Decimal | None,
    monthly_bill: Decimal | None,
    bill_fixed_charge: Decimal | None,
    settings: Settings,
    overrides: Overrides,
) -> Savings:
    validate_overrides(overrides)
    generation = kw * settings.generation_kwh_per_kw_year
    pct = (
        overrides.usable_generation_pct
        if overrides.usable_generation_pct is not None
        else settings.usable_generation_pct
    )
    if overrides.fixed_charge_monthly is not None:
        fixed, source = overrides.fixed_charge_monthly, "override"
    elif bill_fixed_charge is not None:
        fixed, source = bill_fixed_charge, "bill"
    else:
        fixed, source = settings.default_fixed_charge_monthly, "default"

    def unavailable(reason: str, usable: Decimal = ZERO, rate: Decimal | None = None) -> Savings:
        return Savings(
            whole(generation), usable, pct, fixed, source, rate, None, "not_available", reason
        )

    if not avg_monthly_units or monthly_bill is None:
        return unavailable("needs_bill_units")
    usable = min(generation * pct, avg_monthly_units * 12)
    rate = overrides.savings_rate
    if rate is None:
        rate = (monthly_bill - fixed) / avg_monthly_units
    if rate <= 0:
        return unavailable("savings_rate_not_positive", usable, rate)
    annual = rupees(usable * rate)
    # §10: the estimate can never exceed the variable part of the current bill. The natural rate
    # can't (usable is capped at consumption); an override could, so it is rejected, not trimmed.
    if overrides.savings_rate is not None and annual > rupees((monthly_bill - fixed) * 12):
        raise CalcError(
            "INVALID_INPUT",
            "That saving per unit would save more than the whole bill.",
            fields=["savings_rate"],
        )
    if annual <= 0:
        return unavailable("savings_not_positive", usable, rate)
    return Savings(whole(generation), usable, pct, fixed, source, rate, annual, "ok", None)


def payback(net_cost: Decimal, annual_savings: Decimal | None) -> Payback:
    """Simple payback on the rounded savings shown to the customer, so the numbers reconcile."""
    if net_cost <= 0:
        return Payback(ZERO, "immediate")
    if annual_savings is None or annual_savings <= 0:
        return Payback(None, "not_available")
    return Payback(one_decimal(net_cost / annual_savings), "ok")
