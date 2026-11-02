"""Solar sizing (ARCHITECTURE §8).

Recommendations are *provisional* until a person verifies the roof area (survey or call);
quotes need the *final* one. Sanctioned load is flagged, never used to cap silently.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.services.calc.errors import CalcError
from app.services.calc.types import Settings

MONTHS = Decimal("12")


@dataclass(frozen=True)
class Sizing:
    annual_units: Decimal
    required_kw: Decimal  # exact, never rounded
    kw_by_usage: Decimal
    kw_by_roof: Decimal | None  # None: roof unknown or too small (see flags)
    recommended_kw: Decimal | None  # None for tenants or when no option fits the roof
    status: Literal["provisional", "final"]
    roof_basis: Literal["verified", "declared", "none"]
    flags: tuple[str, ...]


def _positive(name: str, value: Decimal) -> Decimal:
    if value <= 0:
        raise CalcError("INVALID_INPUT", f"{name} must be greater than zero.", field=name)
    return value


def annual_units(avg_monthly_units: Decimal) -> Decimal:
    """0 is valid (vacant home, new connection) and sizes nothing; negative is an input error."""
    if avg_monthly_units < 0:
        raise CalcError(
            "INVALID_INPUT", "avg_monthly_units cannot be negative.", field="avg_monthly_units"
        )
    return avg_monthly_units * MONTHS


def required_kw(annual: Decimal, settings: Settings) -> Decimal:
    return annual / settings.generation_kwh_per_kw_year


def kw_by_usage(required: Decimal, settings: Settings) -> tuple[Decimal, tuple[str, ...]]:
    """Smallest capacity option that covers the need; the largest one if none does."""
    for option in settings.capacity_options_kw:
        if option >= required:
            return option, ()
    return settings.capacity_options_kw[-1], ("usage_exceeds_max_option",)


def kw_by_roof(roof_sqft: Decimal, settings: Settings) -> Decimal | None:
    """Largest capacity option the roof can hold, or None if not even the smallest fits."""
    capacity = roof_sqft / settings.roof_sqft_per_kw
    fitting = [o for o in settings.capacity_options_kw if o <= capacity]
    return fitting[-1] if fitting else None


def recommend(
    *,
    ownership: Literal["owner", "tenant"],
    avg_monthly_units: Decimal | None,
    declared_roof_sqft: Decimal | None,
    verified_roof_sqft: Decimal | None,
    sanctioned_load_kw: Decimal | None,
    settings: Settings,
) -> Sizing:
    if avg_monthly_units is None:
        raise CalcError("USAGE_UNKNOWN", "Monthly units are needed to size a system.")
    annual = annual_units(avg_monthly_units)
    required = required_kw(annual, settings)
    by_usage, flags = kw_by_usage(required, settings)
    flag_list = list(flags)

    if verified_roof_sqft is not None:
        roof, basis = _positive("verified_roof_sqft", verified_roof_sqft), "verified"
    elif declared_roof_sqft is not None:
        roof, basis = _positive("declared_roof_sqft", declared_roof_sqft), "declared"
    else:
        roof, basis = None, "none"
    by_roof = kw_by_roof(roof, settings) if roof is not None else None

    if basis != "verified":
        flag_list.append("roof_unverified")
    if roof is not None and by_roof is None:
        flag_list.append("roof_too_small")

    if annual == 0:
        flag_list.append("usage_zero")

    if ownership == "tenant":
        recommended = None  # initial rules: no recommendation for tenants (§2 owner revision)
    elif annual == 0:
        recommended = None  # nothing to offset; scored Low with reason usage_zero
    elif roof is None:
        recommended = by_usage  # consumption only, provisional
    elif by_roof is None:
        recommended = None
    else:
        recommended = min(by_usage, by_roof)

    if sanctioned_load_kw is None:
        flag_list.append("sanctioned_load_unknown")
    elif recommended is not None and recommended > sanctioned_load_kw:
        flag_list.append("exceeds_sanctioned_load")

    return Sizing(
        annual_units=annual,
        required_kw=required,
        kw_by_usage=by_usage,
        kw_by_roof=by_roof,
        recommended_kw=recommended,
        status="final" if basis == "verified" else "provisional",
        roof_basis=basis,
        flags=tuple(flag_list),
    )
