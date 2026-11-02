"""Solar sizing (ARCHITECTURE §8, §8.1).

annual_units   = avg_monthly_units × 12
required_kw    = annual_units ÷ 1,400                       (exact Decimal)
kw_by_usage    = smallest capacity option ≥ required_kw
kw_by_roof     = largest capacity option ≤ roof_area ÷ 100  (A-2)
recommended_kw = min(kw_by_usage, kw_by_roof); tenants → none
Provisional until roof area is verified; sanctioned load only flags, never caps.
"""

from decimal import Decimal as D

import pytest

from app.services.calc.errors import CalcError
from app.services.calc.sizing import annual_units, kw_by_roof, kw_by_usage, recommend, required_kw


def size(settings, units, ownership="owner", declared=None, verified=None, load=None):
    return recommend(
        ownership=ownership,
        avg_monthly_units=units,
        declared_roof_sqft=declared,
        verified_roof_sqft=verified,
        sanctioned_load_kw=load,
        settings=settings,
    )


# --- The brief's sample leads: roof area, sanctioned load and tariff are not given ---


def test_prashant_340_units_is_3kw_provisional(settings):
    s = size(settings, D("340"))
    assert s.annual_units == D("4080")
    assert s.required_kw == D("4080") / D("1400")  # 2.914…
    assert s.kw_by_usage == D("3")
    assert s.kw_by_roof is None
    assert s.recommended_kw == D("3")
    assert s.status == "provisional"
    assert "roof_unverified" in s.flags and "sanctioned_load_unknown" in s.flags


def test_rohit_tenant_gets_no_recommendation(settings):
    s = size(settings, D("210"), ownership="tenant")
    assert s.annual_units == D("2520")
    assert s.recommended_kw is None


def test_ayesha_85_units_is_1kw_provisional(settings):
    s = size(settings, D("85"))
    assert s.annual_units == D("1020")
    assert s.kw_by_usage == D("1")
    assert s.recommended_kw == D("1")
    assert s.status == "provisional"


# --- Boundaries and constraints ---


def test_exactly_350_units_is_3kw_not_4(settings):
    assert required_kw(annual_units(D("350")), settings) == D("3")
    assert size(settings, D("350")).recommended_kw == D("3")


def test_351_units_rounds_up_to_4kw(settings):
    assert size(settings, D("351")).recommended_kw == D("4")


def test_usage_above_largest_option_uses_largest_and_flags(settings):
    value, flags = kw_by_usage(D("12"), settings)
    assert value == D("10")
    assert flags == ("usage_exceeds_max_option",)


def test_roof_capacity(settings):
    assert kw_by_roof(D("250"), settings) == D("2")
    assert kw_by_roof(D("100"), settings) == D("1")
    assert kw_by_roof(D("99"), settings) is None
    assert kw_by_roof(D("5000"), settings) == D("10")


def test_roof_limits_usage(settings):
    s = size(settings, D("340"), declared=D("250"))
    assert s.kw_by_usage == D("3")
    assert s.kw_by_roof == D("2")
    assert s.recommended_kw == D("2")
    assert s.roof_basis == "declared"
    assert s.status == "provisional"


def test_verified_roof_makes_it_final_and_wins_over_declared(settings):
    s = size(settings, D("340"), declared=D("250"), verified=D("450"), load=D("5"))
    assert s.kw_by_roof == D("4")
    assert s.recommended_kw == D("3")
    assert s.roof_basis == "verified"
    assert s.status == "final"
    assert s.flags == ()


def test_roof_too_small_gives_no_recommendation(settings):
    s = size(settings, D("340"), declared=D("80"))
    assert s.recommended_kw is None
    assert "roof_too_small" in s.flags


def test_sanctioned_load_below_recommendation_flags_without_capping(settings):
    s = size(settings, D("340"), verified=D("450"), load=D("2"))
    assert s.recommended_kw == D("3")
    assert "exceeds_sanctioned_load" in s.flags


def test_unknown_usage_is_an_error(settings):
    with pytest.raises(CalcError) as err:
        size(settings, None)
    assert err.value.code == "USAGE_UNKNOWN"


def test_negative_usage_is_invalid(settings):
    with pytest.raises(CalcError) as err:
        size(settings, D("-1"))
    assert err.value.code == "INVALID_INPUT"


def test_zero_usage_sizes_nothing_and_is_flagged(settings):
    """Review fix 3 / §15.1: annual consumption 0 → 0 (vacant home, new connection)."""
    assert annual_units(D("0")) == D("0")
    s = size(settings, D("0"), declared=D("450"))
    assert s.annual_units == D("0")
    assert s.recommended_kw is None
    assert "usage_zero" in s.flags


def test_negative_roof_is_invalid(settings):
    with pytest.raises(CalcError) as err:
        size(settings, D("340"), declared=D("-5"))
    assert err.value.code == "INVALID_INPUT"
