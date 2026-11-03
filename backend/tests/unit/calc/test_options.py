"""Quote options respect verified roof capacity and sanctioned load (ARCHITECTURE §8, §10.1).

max_allowed = min(kW by verified roof, sanctioned load, largest option)
candidates  = recommended + offsets (−1, 0, +1, A-10)
anything above max_allowed is removed, with the reason.
"""

from decimal import Decimal as D

import pytest

from app.services.calc.errors import CalcError
from app.services.calc.options import quote_options


def options(settings, rec, roof, load):
    return quote_options(
        recommended_kw=rec, verified_roof_sqft=roof, sanctioned_load_kw=load, settings=settings
    )


def test_roof_450_load_5_offers_2_3_4(settings):
    result = options(settings, D("3"), D("450"), D("5"))
    assert result.offered == (D("2"), D("3"), D("4"))
    assert result.removed == ()


def test_load_3_removes_4kw(settings):
    result = options(settings, D("3"), D("450"), D("3"))
    assert result.offered == (D("2"), D("3"))
    assert result.removed == ({"kw": "4", "reason": "sanctioned_load"},)


def test_roof_250_recommends_2_and_removes_3_for_roof(settings):
    # With roof 250 the final recommendation is 2 kW (sizing), so candidates are 1, 2, 3.
    result = options(settings, D("2"), D("250"), D("5"))
    assert result.offered == (D("1"), D("2"))
    assert result.removed == ({"kw": "3", "reason": "roof"},)


def test_recommendation_above_load_is_not_offered(settings):
    result = options(settings, D("3"), D("450"), D("2"))
    assert result.offered == (D("2"),)
    assert {"kw": "3", "reason": "sanctioned_load"} in result.removed


def test_smallest_option_never_goes_below_one_kw(settings):
    result = options(settings, D("1"), D("450"), D("5"))
    assert result.offered == (D("1"), D("2"))


def test_offsets_step_through_non_contiguous_options():
    """Review fix 1: offsets are steps in the option list, not raw kW."""
    from tests.unit.calc.conftest import make_settings

    sparse = make_settings(capacity_options_kw=tuple(D(n) for n in (1, 2, 3, 5, 7, 10)))
    result = quote_options(
        recommended_kw=D("5"),
        verified_roof_sqft=D("2000"),
        sanctioned_load_kw=D("20"),
        settings=sparse,
    )
    assert result.offered == (D("3"), D("5"), D("7"))


def test_offsets_step_through_half_kw_options():
    from tests.unit.calc.conftest import make_settings

    halves = make_settings(capacity_options_kw=tuple(D(n) / 2 for n in range(2, 21)))
    result = quote_options(
        recommended_kw=D("2.5"),
        verified_roof_sqft=D("2000"),
        sanctioned_load_kw=D("20"),
        settings=halves,
    )
    assert result.offered == (D("2"), D("2.5"), D("3"))


def test_recommendation_must_be_a_configured_option(settings):
    with pytest.raises(CalcError) as err:
        options(settings, D("2.5"), D("450"), D("5"))
    assert err.value.code == "INVALID_INPUT"


def test_tiny_roof_has_no_option(settings):
    with pytest.raises(CalcError) as err:
        options(settings, None, D("80"), D("5"))
    assert err.value.code == "NO_OPTION_FITS"


def test_sanctioned_load_below_smallest_option_has_no_option(settings):
    with pytest.raises(CalcError) as err:
        options(settings, D("1"), D("450"), D("0.5"))
    assert err.value.code == "NO_OPTION_FITS"


def test_quote_needs_verified_roof(settings):
    with pytest.raises(CalcError) as err:
        options(settings, D("3"), None, D("5"))
    assert err.value.code == "ROOF_NOT_VERIFIED"


def test_quote_needs_sanctioned_load(settings):
    with pytest.raises(CalcError) as err:
        options(settings, D("3"), D("450"), None)
    assert err.value.code == "SANCTIONED_LOAD_UNKNOWN"


def test_no_usage_says_so_rather_than_blaming_the_roof(settings):
    """Break test: 0 units on a big roof said "No system fits the verified roof"."""
    with pytest.raises(CalcError) as err:
        options(settings, None, D("5000"), D("20"))
    assert err.value.code == "NO_RECOMMENDATION"
