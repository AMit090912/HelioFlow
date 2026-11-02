"""Lead scoring (ARCHITECTURE §7). Deterministic and explainable; Low never rejects.

reasons: tenant · bill_below_threshold (₹1,000, A-1) · roof_too_small · usage_unknown (A-15)
score = low if any reason else high; next_action = call if low else survey_visit
"""

from decimal import Decimal as D

import pytest

from app.services.calc.scoring import score_lead
from app.services.calc.sizing import recommend


def sizing(settings, units, ownership="owner", roof=None):
    return recommend(
        ownership=ownership,
        avg_monthly_units=units,
        declared_roof_sqft=roof,
        verified_roof_sqft=None,
        sanctioned_load_kw=None,
        settings=settings,
    )


def codes(score):
    return [r["code"] for r in score.reasons]


def test_prashant_is_high_and_gets_a_visit(settings):
    s = score_lead("owner", D("3200"), "declared", sizing(settings, D("340")), settings)
    assert (s.score, s.next_action, s.reasons) == ("high", "survey_visit", ())


def test_rohit_tenant_is_low_and_gets_a_call(settings):
    s = score_lead("tenant", D("1900"), "declared", sizing(settings, D("210"), "tenant"), settings)
    assert (s.score, s.next_action) == ("low", "call")
    assert codes(s) == ["tenant"]


def test_ayesha_small_bill_is_low_with_explained_reason(settings):
    s = score_lead("owner", D("650"), "declared", sizing(settings, D("85")), settings)
    assert (s.score, s.next_action) == ("low", "call")
    assert s.reasons == (
        {"code": "bill_below_threshold", "value": "650", "threshold": "1000", "source": "declared"},
    )


@pytest.mark.parametrize(("bill", "expected"), [("999", "low"), ("1000", "high"), ("1001", "high")])
def test_threshold_boundary(settings, bill, expected):
    assert (
        score_lead("owner", D(bill), "declared", sizing(settings, D("340")), settings).score
        == expected
    )


def test_confirmed_bill_source_is_recorded(settings):
    s = score_lead("owner", D("820"), "confirmed", sizing(settings, D("100")), settings)
    assert s.reasons[0]["source"] == "confirmed"


def test_threshold_is_read_from_settings(settings):
    from tests.unit.calc.conftest import make_settings

    strict = make_settings(min_monthly_bill_for_survey=D("2000"))
    s = score_lead("owner", D("1900"), "declared", sizing(strict, D("210")), strict)
    assert s.reasons[0]["threshold"] == "2000"


def test_roof_too_small_is_a_low_reason(settings):
    s = score_lead(
        "owner", D("3200"), "declared", sizing(settings, D("340"), roof=D("80")), settings
    )
    assert codes(s) == ["roof_too_small"]


def test_unknown_usage_is_a_low_reason(settings):
    s = score_lead("owner", D("3200"), "declared", None, settings)
    assert codes(s) == ["usage_unknown"]
    assert s.next_action == "call"


def test_zero_usage_is_a_low_reason(settings):
    s = score_lead("owner", D("3200"), "confirmed", sizing(settings, D("0")), settings)
    assert codes(s) == ["usage_zero"]
    assert s.next_action == "call"


def test_reasons_combine_in_a_stable_order(settings):
    s = score_lead("tenant", D("500"), "declared", None, settings)
    assert codes(s) == ["tenant", "bill_below_threshold", "usage_unknown"]


def test_low_never_means_rejected(settings):
    s = score_lead("tenant", D("100"), "declared", None, settings)
    assert s.score in {"high", "low"}
    assert s.next_action in {"survey_visit", "call"}
