"""Effective-dated rule selection (§9.1, §9.2, §9.3).

Inclusive at both ends; `effective_to=None` is open-ended. No match is an explicit
error: an expired rule is never reused and a missing subsidy is never assumed to be zero.
"""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.services.calc.errors import CalcError
from app.services.calc.types import PriceRule, SubsidyRule


class _Dated(Protocol):
    id: str
    effective_from: date
    effective_to: date | None


def is_effective(rule: _Dated, on: date) -> bool:
    return rule.effective_from <= on and (rule.effective_to is None or on <= rule.effective_to)


def _single[R: _Dated](matches: list[R], missing_code: str, what: str, on: date) -> R:
    if not matches:
        raise CalcError(missing_code, f"No {what} applies on {on.isoformat()}.", on=on.isoformat())
    if len(matches) > 1:
        raise CalcError(
            "RULE_AMBIGUOUS",
            f"More than one {what} applies on {on.isoformat()}.",
            rule_ids=[m.id for m in matches],
        )
    return matches[0]


def select_price_rule(rules: Iterable[PriceRule], kw: Decimal, on: date) -> PriceRule:
    matches = [r for r in rules if is_effective(r, on) and r.min_kw <= kw <= r.max_kw]
    return _single(matches, "PRICE_RULE_MISSING", f"price rule for {kw} kW", on)


def select_subsidy_rule(
    rules: Iterable[SubsidyRule], segment: str, on: date, scheme: str = "CENTRAL_RESIDENTIAL"
) -> SubsidyRule:
    matches = [
        r for r in rules if r.scheme_code == scheme and r.segment == segment and is_effective(r, on)
    ]
    return _single(matches, "SUBSIDY_RULE_MISSING", f"{scheme} subsidy rule", on)
