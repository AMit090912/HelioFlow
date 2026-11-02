"""DB → engine adapter: seeded rules and settings drive the same numbers as the unit tests."""

from datetime import date
from decimal import Decimal as D

import pytest
from sqlalchemy.orm import Session

from app.models import Setting, SubsidyRule
from app.models.enums import SubsidySegment
from app.services.calc.engine import QuoteInputs, build_quote_options
from app.services.calc.errors import CalcError
from app.services.calc.savings import Overrides
from app.services.rules_repo import load_price_rules, load_settings, load_subsidy_rules
from seed import run as seed

ON = date(2026, 11, 2)


@pytest.fixture
def seeded(db_session: Session) -> Session:
    seed(db_session, "demo-pass-for-tests")
    return db_session


def test_settings_match_the_spec(seeded: Session):
    s = load_settings(seeded)
    assert s.generation_kwh_per_kw_year == D("1400")
    assert s.roof_sqft_per_kw == D("100")
    assert s.min_monthly_bill_for_survey == D("1000")
    assert s.capacity_options_kw == tuple(D(n) for n in range(1, 11))
    assert s.usable_generation_pct == D("0.90")
    assert s.default_fixed_charge_monthly == D("150")
    assert s.quote_option_offsets == (-1, 0, 1)


def test_prashant_through_db_rules_matches_unit_numbers(seeded: Session):
    inputs = QuoteInputs(
        ownership="owner",
        property_type="home",
        avg_monthly_units=D("340"),
        monthly_bill=D("3200"),
        declared_roof_sqft=D("450"),
        verified_roof_sqft=D("450"),
        sanctioned_load_kw=D("5"),
        bill_fixed_charge=None,
    )
    result = build_quote_options(
        inputs=inputs,
        price_rules=load_price_rules(seeded),
        subsidy_rules=load_subsidy_rules(seeded),
        settings=load_settings(seeded),
        on=ON,
        overrides=Overrides(),
    )
    three = next(q for q in result.quotes if q.kw == D("3"))
    assert (
        three.gross,
        three.subsidy.amount,
        three.net,
        three.savings.annual_savings,
        three.payback.years,
    ) == (
        D("180000"),
        D("78000"),
        D("102000"),
        D("33909"),
        D("3.0"),
    )
    assert three.subsidy.rule.source_note.startswith("Client-stated figures")


def test_missing_setting_is_reported(seeded: Session):
    seeded.delete(seeded.get(Setting, "roof_sqft_per_kw"))
    seeded.flush()
    with pytest.raises(CalcError) as err:
        load_settings(seeded)
    assert err.value.code == "SETTINGS_INCOMPLETE"
    assert "roof_sqft_per_kw" in err.value.context["missing"]


def test_out_of_range_setting_is_rejected(seeded: Session):
    seeded.get(Setting, "usable_generation_pct").value = "1.5"
    seeded.flush()
    with pytest.raises(CalcError) as err:
        load_settings(seeded)
    assert err.value.code == "SETTINGS_INVALID"


@pytest.mark.parametrize(
    "slabs",
    [
        [],
        [{"from_kw": "0", "to_kw": "2"}],
        [{"from_kw": "0", "to_kw": "2", "amount_per_kw": "-1"}],
        [{"from_kw": "0", "to_kw": "0", "amount_per_kw": "30000"}],
    ],
    ids=["empty", "missing-amount", "negative-amount", "zero-width"],
)
def test_malformed_slabs_are_rejected(seeded: Session, slabs):
    seeded.add(
        SubsidyRule(
            scheme_code="BROKEN",
            segment=SubsidySegment.residential,
            slabs=slabs,
            cap_amount=D("78000"),
            effective_from=date(2026, 1, 1),
            source_note="bad",
        )
    )
    seeded.flush()
    with pytest.raises(CalcError) as err:
        load_subsidy_rules(seeded)
    assert err.value.code == "INVALID_RULE"


def test_non_contiguous_slabs_are_rejected(seeded: Session):
    seeded.add(
        SubsidyRule(
            scheme_code="BROKEN",
            segment=SubsidySegment.residential,
            slabs=[
                {"from_kw": "0", "to_kw": "2", "amount_per_kw": "30000"},
                {"from_kw": "2.5", "to_kw": "3", "amount_per_kw": "18000"},
            ],
            cap_amount=D("78000"),
            effective_from=date(2026, 1, 1),
            source_note="bad",
        )
    )
    seeded.flush()
    with pytest.raises(CalcError) as err:
        load_subsidy_rules(seeded)
    assert err.value.code == "INVALID_RULE"
