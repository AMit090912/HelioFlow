"""Effective-dated rule selection and rounding (ARCHITECTURE §9.3, §15.1).

Effective dates are inclusive at both ends; effective_to=None is open-ended.
A missing rule is an explicit error, never an expired rule and never zero.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from app.services.calc.errors import CalcError
from app.services.calc.rounding import one_decimal, rupees, whole
from app.services.calc.rules import is_effective, select_price_rule, select_subsidy_rule
from tests.unit.calc.conftest import price_rule, subsidy_rule


def test_rounding_is_half_up_at_outputs():
    assert rupees(D("33908.5")) == D("33909")
    assert rupees(D("33908.49")) == D("33908")
    assert one_decimal(D("2.25")) == D("2.3")  # banker's rounding would give 2.2
    assert one_decimal(D("2.95")) == D("3.0")
    assert whole(D("4199.5")) == 4200


def test_effective_dates_inclusive_at_both_ends():
    rule = subsidy_rule(effective_from=date(2026, 4, 1), effective_to=date(2026, 12, 31))
    assert not is_effective(rule, date(2026, 3, 31))
    assert is_effective(rule, date(2026, 4, 1))
    assert is_effective(rule, date(2026, 12, 31))
    assert not is_effective(rule, date(2027, 1, 1))


def test_open_ended_rule_applies_forever_after_start():
    assert is_effective(subsidy_rule(effective_to=None), date(2099, 1, 1))


def test_rule_change_switches_on_the_new_rule_date():
    a = subsidy_rule(id="A", effective_to=date(2026, 11, 30))
    b = subsidy_rule(id="B", effective_from=date(2026, 12, 1), cap_amount=D("70000"))
    assert select_subsidy_rule([a, b], "residential", date(2026, 11, 30)).id == "A"
    assert select_subsidy_rule([a, b], "residential", date(2026, 12, 1)).id == "B"


def test_expired_rule_is_never_used():
    only = subsidy_rule(effective_to=date(2026, 6, 30))
    with pytest.raises(CalcError) as err:
        select_subsidy_rule([only], "residential", date(2026, 11, 2))
    assert err.value.code == "SUBSIDY_RULE_MISSING"


def test_no_rules_is_an_explicit_error():
    with pytest.raises(CalcError) as err:
        select_subsidy_rule([], "residential", date(2026, 11, 2))
    assert err.value.code == "SUBSIDY_RULE_MISSING"


def test_price_rule_selected_by_kw_and_date():
    rule = price_rule()
    assert select_price_rule([rule], D("3"), date(2026, 11, 2)) is rule
    assert select_price_rule([rule], D("10"), date(2026, 11, 2)) is rule  # max inclusive


def test_kw_outside_every_price_range_is_missing():
    with pytest.raises(CalcError) as err:
        select_price_rule([price_rule()], D("12"), date(2026, 11, 2))
    assert err.value.code == "PRICE_RULE_MISSING"


def test_price_rule_before_start_date_is_missing():
    with pytest.raises(CalcError) as err:
        select_price_rule([price_rule()], D("3"), date(2025, 12, 31))
    assert err.value.code == "PRICE_RULE_MISSING"


def test_two_matching_rules_are_ambiguous():
    # The database forbids overlaps; the engine still refuses to guess if handed bad data.
    with pytest.raises(CalcError) as err:
        select_price_rule([price_rule(id="x"), price_rule(id="y")], D("3"), date(2026, 11, 2))
    assert err.value.code == "RULE_AMBIGUOUS"
