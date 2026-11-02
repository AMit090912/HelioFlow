"""Lead scoring (ARCHITECTURE §7): transparent rules on confirmed inputs.

A Low score only swaps the survey visit for a call; nothing here rejects a lead [CLIENT].
Each reason records the values it was judged on, so later threshold edits never rewrite history.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.services.calc.sizing import Sizing
from app.services.calc.types import Settings


@dataclass(frozen=True)
class Score:
    score: Literal["high", "low"]
    next_action: Literal["survey_visit", "call"]
    reasons: tuple[dict[str, str], ...]


def score_lead(
    ownership: Literal["owner", "tenant"],
    bill_amount: Decimal,
    bill_source: Literal["declared", "confirmed"],
    sizing: Sizing | None,
    settings: Settings,
) -> Score:
    """`sizing` is None when monthly units are unknown (e.g. the bill could not be read)."""
    reasons: list[dict[str, str]] = []
    if ownership == "tenant":
        reasons.append({"code": "tenant"})
    threshold = settings.min_monthly_bill_for_survey
    if bill_amount < threshold:
        reasons.append(
            {
                "code": "bill_below_threshold",
                "value": str(bill_amount),
                "threshold": str(threshold),
                "source": bill_source,
            }
        )
    if sizing is not None and "roof_too_small" in sizing.flags:
        reasons.append({"code": "roof_too_small"})
    if sizing is None:
        reasons.append({"code": "usage_unknown"})
    elif "usage_zero" in sizing.flags:
        reasons.append({"code": "usage_zero"})

    if reasons:
        return Score("low", "call", tuple(reasons))
    return Score("high", "survey_visit", ())
