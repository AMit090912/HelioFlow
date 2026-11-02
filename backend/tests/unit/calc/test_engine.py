"""End-to-end engine: the sample quote rows in ARCHITECTURE §10.1, with verified roof and load."""

from dataclasses import fields, is_dataclass
from datetime import date
from decimal import Decimal as D

import pytest

from app.services.calc.engine import CALC_VERSION, QuoteInputs, build_quote_options
from app.services.calc.errors import CalcError
from app.services.calc.savings import Overrides
from tests.unit.calc.conftest import QUOTE_DAY, price_rule, subsidy_rule

PRASHANT = QuoteInputs(
    ownership="owner",
    property_type="home",
    avg_monthly_units=D("340"),
    monthly_bill=D("3200"),
    declared_roof_sqft=D("450"),
    verified_roof_sqft=D("450"),
    sanctioned_load_kw=D("5"),
    bill_fixed_charge=None,
)


def build(settings, inputs=PRASHANT, on=QUOTE_DAY, overrides=None, prices=None, subsidies=None):
    return build_quote_options(
        inputs=inputs,
        price_rules=prices or [price_rule()],
        subsidy_rules=subsidies if subsidies is not None else [subsidy_rule()],
        settings=settings,
        on=on,
        overrides=overrides or Overrides(),
    )


def row(q):
    return (
        q.kw,
        q.gross,
        q.subsidy.amount,
        q.net,
        q.savings.usable_generation,
        q.savings.annual_savings,
        q.payback.years,
    )


def test_prashant_three_options_match_the_spec(settings):
    result = build(settings)
    assert result.recommended_kw == D("3")
    assert [row(q) for q in result.quotes] == [
        (D("2"), D("120000"), D("60000"), D("60000"), D("2520.00"), D("22606"), D("2.7")),
        (D("3"), D("180000"), D("78000"), D("102000"), D("3780.00"), D("33909"), D("3.0")),
        (D("4"), D("240000"), D("78000"), D("162000"), D("4080"), D("36600"), D("4.4")),
    ]
    assert [q.recommended for q in result.quotes] == [False, True, False]
    assert result.calc_version == CALC_VERSION


def test_ayesha_1kw(settings):
    ayesha = QuoteInputs(
        ownership="owner",
        property_type="home",
        avg_monthly_units=D("85"),
        monthly_bill=D("650"),
        declared_roof_sqft=D("200"),
        verified_roof_sqft=D("200"),
        sanctioned_load_kw=D("2"),
        bill_fixed_charge=None,
    )
    result = build(settings, inputs=ayesha)
    one = next(q for q in result.quotes if q.kw == D("1"))
    assert row(one) == (D("1"), D("60000"), D("30000"), D("30000"), D("1020"), D("6000"), D("5.0"))


def test_records_rules_and_assumptions_for_the_snapshot(settings):
    result = build(settings)
    q = result.quotes[1]
    assert q.price_rule.id == "price-1"
    assert q.subsidy.rule is not None and q.subsidy.rule.id == "subsidy-1"
    assert {"A-3", "A-4", "A-6", "A-7", "A-8", "A-11", "A-13"} <= set(result.assumptions)
    assert result.priced_on == QUOTE_DAY


def test_tenant_cannot_be_quoted_and_is_told_why(settings):
    """Review fix 5: the reason is tenancy, not the (perfectly good) roof."""
    tenant = QuoteInputs(**{**PRASHANT.__dict__, "ownership": "tenant"})
    with pytest.raises(CalcError) as err:
        build(settings, inputs=tenant)
    assert err.value.code == "NOT_QUOTABLE_TENANT"


def test_result_carries_settings_and_inputs_for_the_snapshot(settings):
    """Review fix 4 / §3.7, §11: a quote records the settings and inputs it was priced with."""
    from tests.unit.calc.conftest import make_settings

    edited = make_settings(generation_kwh_per_kw_year=D("1350"))
    result = build(edited)
    assert result.settings is edited
    assert result.inputs is PRASHANT
    three = next(q for q in result.quotes if q.kw == D("3"))
    assert three.savings.annual_generation == 4050  # 3 × 1,350


def test_ex_gst_price_rule_is_refused(settings):
    """Review fix 6: no GST rate is configured, so an ex-GST price cannot be quoted honestly."""
    with pytest.raises(CalcError) as err:
        build(settings, prices=[price_rule(gst_inclusive=False)])
    assert err.value.code == "PRICE_RULE_UNSUPPORTED"


def test_missing_subsidy_rule_blocks_the_quote(settings):
    with pytest.raises(CalcError) as err:
        build(settings, subsidies=[subsidy_rule(effective_to=date(2026, 1, 1))])
    assert err.value.code == "SUBSIDY_RULE_MISSING"


def test_business_quote_has_no_subsidy(settings):
    biz = QuoteInputs(**{**PRASHANT.__dict__, "property_type": "business"})
    q = build(settings, inputs=biz, subsidies=[]).quotes[1]
    assert (q.subsidy.status, q.subsidy.amount, q.net) == ("NOT_ELIGIBLE", D("0"), D("180000"))


def test_net_never_goes_negative(settings):
    cheap = [price_rule(price_per_kw=D("10000"))]
    q = build(settings, prices=cheap).quotes[1]  # gross 30,000 < subsidy 78,000
    assert q.net == D("0")
    assert "net_floored_at_zero" in q.flags
    assert q.payback.status == "immediate"


def _numbers(value):
    if is_dataclass(value):
        for f in fields(value):
            yield from _numbers(getattr(value, f.name))
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from _numbers(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _numbers(item)
    elif isinstance(value, (int, float, D)) and not isinstance(value, bool):
        yield value


def test_no_floats_anywhere_in_the_result(settings):
    assert not [n for n in _numbers(build(settings)) if isinstance(n, float)]
