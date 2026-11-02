"""Quote option engine: sizing → constraint-filtered options → price, subsidy, savings, payback.

The result is everything a quote snapshot needs (§11): inputs-derived numbers, the exact rule
rows used, the overrides, the assumption ids and the calc version. Pure: no I/O.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from app.services.calc.errors import CalcError
from app.services.calc.options import OptionSet, quote_options
from app.services.calc.pricing import Subsidy, gross_cost, subsidy_for
from app.services.calc.rules import select_price_rule
from app.services.calc.savings import Overrides, Payback, Savings, estimate_savings, payback
from app.services.calc.sizing import Sizing, recommend
from app.services.calc.types import PriceRule, Settings, SubsidyRule

CALC_VERSION = "calc-1.0.0"
# Assumptions every quote depends on (ARCHITECTURE §17), stored with the snapshot.
QUOTE_ASSUMPTIONS = (
    "A-2",
    "A-3",
    "A-4",
    "A-5",
    "A-6",
    "A-7",
    "A-8",
    "A-9",
    "A-10",
    "A-11",
    "A-13",
    "A-19",
    "A-20",
)
ZERO = Decimal("0")


@dataclass(frozen=True)
class QuoteInputs:
    ownership: Literal["owner", "tenant"]
    property_type: Literal["home", "business"]
    avg_monthly_units: Decimal | None
    monthly_bill: Decimal | None  # confirmed bill amount, else declared
    declared_roof_sqft: Decimal | None
    verified_roof_sqft: Decimal | None
    sanctioned_load_kw: Decimal | None
    bill_fixed_charge: Decimal | None


@dataclass(frozen=True)
class OptionQuote:
    kw: Decimal
    recommended: bool
    price_rule: PriceRule
    gross: Decimal
    subsidy: Subsidy
    net: Decimal
    savings: Savings
    payback: Payback
    flags: tuple[str, ...]


@dataclass(frozen=True)
class QuoteOptions:
    """Everything the immutable quote snapshot (§11) needs, including the inputs and the
    settings values used — settings are not date-versioned, so the quote must keep them (§3.7)."""

    priced_on: date
    calc_version: str
    inputs: QuoteInputs
    settings: Settings
    sizing: Sizing
    options: OptionSet
    recommended_kw: Decimal
    quotes: tuple[OptionQuote, ...]
    overrides: Overrides
    assumptions: tuple[str, ...]


def price_option(
    *,
    kw: Decimal,
    recommended: bool,
    inputs: QuoteInputs,
    price_rules: Sequence[PriceRule],
    subsidy_rules: Sequence[SubsidyRule],
    settings: Settings,
    on: date,
    overrides: Overrides,
) -> OptionQuote:
    rule = select_price_rule(price_rules, kw, on)
    gross = gross_cost(kw, rule)
    subsidy = subsidy_for(kw, inputs.property_type, subsidy_rules, on)
    flags: list[str] = []
    net = gross - subsidy.amount
    if net < 0:
        net, flags = ZERO, ["net_floored_at_zero"]
    savings = estimate_savings(
        kw=kw,
        avg_monthly_units=inputs.avg_monthly_units,
        monthly_bill=inputs.monthly_bill,
        bill_fixed_charge=inputs.bill_fixed_charge,
        settings=settings,
        overrides=overrides,
    )
    return OptionQuote(
        kw=kw,
        recommended=recommended,
        price_rule=rule,
        gross=gross,
        subsidy=subsidy,
        net=net,
        savings=savings,
        payback=payback(net, savings.annual_savings),
        flags=tuple(flags),
    )


def build_quote_options(
    *,
    inputs: QuoteInputs,
    price_rules: Sequence[PriceRule],
    subsidy_rules: Sequence[SubsidyRule],
    settings: Settings,
    on: date,
    overrides: Overrides,
) -> QuoteOptions:
    if inputs.ownership == "tenant":
        raise CalcError(
            "NOT_QUOTABLE_TENANT", "Tenants are not quoted under the initial rules (§2)."
        )
    sizing = recommend(
        ownership=inputs.ownership,
        avg_monthly_units=inputs.avg_monthly_units,
        declared_roof_sqft=inputs.declared_roof_sqft,
        verified_roof_sqft=inputs.verified_roof_sqft,
        sanctioned_load_kw=inputs.sanctioned_load_kw,
        settings=settings,
    )
    option_set = quote_options(
        recommended_kw=sizing.recommended_kw,
        verified_roof_sqft=inputs.verified_roof_sqft,
        sanctioned_load_kw=inputs.sanctioned_load_kw,
        settings=settings,
    )
    assert sizing.recommended_kw is not None  # quote_options raises NO_OPTION_FITS otherwise
    quotes = tuple(
        price_option(
            kw=kw,
            recommended=kw == sizing.recommended_kw,
            inputs=inputs,
            price_rules=price_rules,
            subsidy_rules=subsidy_rules,
            settings=settings,
            on=on,
            overrides=overrides,
        )
        for kw in option_set.offered
    )
    return QuoteOptions(
        priced_on=on,
        calc_version=CALC_VERSION,
        inputs=inputs,
        settings=settings,
        sizing=sizing,
        options=option_set,
        recommended_kw=sizing.recommended_kw,
        quotes=quotes,
        overrides=overrides,
        assumptions=QUOTE_ASSUMPTIONS,
    )
