"""Engine fixtures mirroring the seeded settings and rules (ARCHITECTURE §3.7, §9)."""

from datetime import date
from decimal import Decimal as D

import pytest

from app.services.calc.types import PriceRule, Settings, SubsidyRule, SubsidySlab

QUOTE_DAY = date(2026, 11, 2)


def make_settings(**overrides) -> Settings:
    values = dict(
        generation_kwh_per_kw_year=D("1400"),
        roof_sqft_per_kw=D("100"),
        min_monthly_bill_for_survey=D("1000"),
        capacity_options_kw=tuple(D(n) for n in range(1, 11)),
        usable_generation_pct=D("0.90"),
        default_fixed_charge_monthly=D("150"),
        quote_option_offsets=(-1, 0, 1),
    )
    values.update(overrides)
    return Settings(**values)


def price_rule(**kw) -> PriceRule:
    values = dict(
        id="price-1",
        min_kw=D("1"),
        max_kw=D("10"),
        price_per_kw=D("60000"),
        gst_inclusive=True,
        effective_from=date(2026, 1, 1),
        effective_to=None,
    )
    values.update(kw)
    return PriceRule(**values)


def subsidy_rule(**kw) -> SubsidyRule:
    values = dict(
        id="subsidy-1",
        scheme_code="CENTRAL_RESIDENTIAL",
        segment="residential",
        slabs=(SubsidySlab(D("0"), D("2"), D("30000")), SubsidySlab(D("2"), D("3"), D("18000"))),
        cap_amount=D("78000"),
        effective_from=date(2024, 2, 13),
        effective_to=None,
        source_note="Client-stated figures. Verify before launch.",
    )
    values.update(kw)
    return SubsidyRule(**values)


@pytest.fixture
def settings() -> Settings:
    return make_settings()
