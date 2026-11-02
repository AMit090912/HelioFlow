"""Gross price and effective-dated subsidy (ARCHITECTURE §9)."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from app.services.calc.errors import CalcError
from app.services.calc.rounding import rupees
from app.services.calc.rules import select_subsidy_rule
from app.services.calc.types import PriceRule, SubsidyRule

ZERO = Decimal("0")

# Which subsidy segment a property belongs to. Only residential is eligible initially (A-19).
SEGMENT_BY_PROPERTY: dict[str, str | None] = {"home": "residential", "business": None}


@dataclass(frozen=True)
class SubsidyAmount:
    raw: Decimal  # slab total before the cap
    amount: Decimal  # after the cap, rounded to ₹1
    capped: bool


@dataclass(frozen=True)
class Subsidy:
    status: Literal["ELIGIBLE", "NOT_ELIGIBLE"]
    amount: Decimal
    raw: Decimal
    capped: bool
    rule: SubsidyRule | None


def gross_cost(kw: Decimal, rule: PriceRule) -> Decimal:
    """Prices are GST-inclusive (A-11). No GST rate is configured, so an ex-GST rule is refused
    rather than quoted as if it were the full price."""
    if not rule.gst_inclusive:
        raise CalcError(
            "PRICE_RULE_UNSUPPORTED", "Price rules must be GST-inclusive.", rule_id=rule.id
        )
    return rupees(kw * rule.price_per_kw)


def subsidy_amount(kw: Decimal, rule: SubsidyRule) -> SubsidyAmount:
    """Linear pro-rata within each slab (A-5), then the rule's cap."""
    raw = sum(
        (max(ZERO, min(kw, slab.to_kw) - slab.from_kw) * slab.amount_per_kw for slab in rule.slabs),
        ZERO,
    )
    capped = raw > rule.cap_amount
    return SubsidyAmount(raw=raw, amount=rupees(min(raw, rule.cap_amount)), capped=capped)


def subsidy_for(kw: Decimal, property_type: str, rules: Iterable[SubsidyRule], on: date) -> Subsidy:
    segment = SEGMENT_BY_PROPERTY.get(property_type)
    if segment is None:
        return Subsidy("NOT_ELIGIBLE", ZERO, ZERO, False, None)
    rule = select_subsidy_rule(rules, segment, on)  # raises SUBSIDY_RULE_MISSING, never 0
    result = subsidy_amount(kw, rule)
    return Subsidy("ELIGIBLE", result.amount, result.raw, result.capped, rule)
