"""Pricing and subsidy (ARCHITECTURE §9).

gross   = kW × price_per_kw (dated rule, A-3 placeholder ₹60,000)
raw     = Σ slabs max(0, min(kW, to) − from) × amount_per_kw   (linear pro-rata, A-5)
subsidy = min(raw, cap)                                        (client-stated, A-4)
Business premises are NOT_ELIGIBLE (₹0), distinct from a missing rule (A-19).
"""

from datetime import date
from decimal import Decimal as D

import pytest

from app.services.calc.errors import CalcError
from app.services.calc.pricing import gross_cost, subsidy_amount, subsidy_for
from app.services.calc.types import SubsidySlab
from tests.unit.calc.conftest import QUOTE_DAY, price_rule, subsidy_rule


def test_gross_cost(settings):
    assert gross_cost(D("3"), price_rule()) == D("180000")
    assert gross_cost(D("2.5"), price_rule()) == D("150000")


@pytest.mark.parametrize(
    ("kw", "raw", "amount"),
    [
        ("0.5", "15000", "15000"),
        ("1", "30000", "30000"),
        ("2", "60000", "60000"),
        ("2.5", "69000", "69000"),
        ("3", "78000", "78000"),
        ("5", "78000", "78000"),  # slabs end at 3 kW, so the cap is not what limits it
    ],
)
def test_subsidy_table(kw, raw, amount):
    result = subsidy_amount(D(kw), subsidy_rule())
    assert (result.raw, result.amount) == (D(raw), D(amount))
    assert result.capped is False


def test_cap_applies_when_slabs_exceed_it():
    generous = subsidy_rule(slabs=(SubsidySlab(D("0"), D("10"), D("30000")),))
    result = subsidy_amount(D("5"), generous)
    assert (result.raw, result.amount, result.capped) == (D("150000"), D("78000"), True)


def test_home_is_eligible_and_carries_its_rule():
    result = subsidy_for(D("3"), "home", [subsidy_rule()], QUOTE_DAY)
    assert (result.status, result.amount) == ("ELIGIBLE", D("78000"))
    assert result.rule is not None and result.rule.id == "subsidy-1"


def test_business_is_not_eligible_not_missing():
    result = subsidy_for(D("3"), "business", [], QUOTE_DAY)
    assert (result.status, result.amount, result.rule) == ("NOT_ELIGIBLE", D("0"), None)


def test_home_without_a_rule_is_an_error_not_zero():
    with pytest.raises(CalcError) as err:
        subsidy_for(D("3"), "home", [subsidy_rule(effective_to=date(2026, 1, 1))], QUOTE_DAY)
    assert err.value.code == "SUBSIDY_RULE_MISSING"
