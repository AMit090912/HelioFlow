"""Savings and payback estimates (ARCHITECTURE §10). Never guaranteed, never negative.

generation  = kW × 1,400                                     (kWh/yr)
usable      = min(generation × U, annual_units)              (U = 0.90, A-6; surplus valued ₹0, A-7)
rate        = (monthly_bill − fixed_charge) ÷ avg_units
              fixed: override ▸ bill ▸ ₹150 default (A-8)
savings     = usable × rate                                  → ₹1 HALF_UP
payback     = net ÷ savings (rounded)                        → 0.1 yr HALF_UP
"""

from decimal import Decimal as D

import pytest

from app.services.calc.savings import Overrides, estimate_savings, payback


def est(settings, kw, bill, units, fixed=None, overrides=None):
    return estimate_savings(
        kw=D(kw),
        avg_monthly_units=None if units is None else D(units),
        monthly_bill=None if bill is None else D(bill),
        bill_fixed_charge=None if fixed is None else D(fixed),
        settings=settings,
        overrides=overrides or Overrides(),
    )


def test_prashant_3kw(settings):
    s = est(settings, "3", "3200", "340")
    assert s.annual_generation == 4200
    assert s.usable_generation == D("3780.00")
    assert s.fixed_charge == D("150") and s.fixed_charge_source == "default"
    assert s.savings_rate == D("3050") / D("340")  # 8.9705…
    assert s.annual_savings == D("33909")
    assert s.status == "ok"


def test_ayesha_1kw_usable_is_capped_at_consumption(settings):
    s = est(settings, "1", "650", "85")
    assert s.annual_generation == 1400
    assert s.usable_generation == D("1020")  # min(1260, 1020)
    assert s.annual_savings == D("6000")


def test_oversized_system_cannot_save_more_than_the_variable_bill(settings):
    s = est(settings, "4", "3200", "340")
    assert s.usable_generation == D("4080")  # capped at annual consumption
    assert s.annual_savings == D("36600")  # = (3200 − 150) × 12


def test_fixed_charge_from_the_bill_beats_the_default(settings):
    s = est(settings, "3", "3200", "340", fixed="200")
    assert (s.fixed_charge, s.fixed_charge_source) == (D("200"), "bill")


def test_overrides_are_applied_and_recorded(settings):
    s = est(
        settings,
        "3",
        "3200",
        "340",
        fixed="200",
        overrides=Overrides(
            usable_generation_pct=D("0.8"),
            fixed_charge_monthly=D("180"),
        ),
    )
    assert s.usable_generation_pct == D("0.8")
    assert (s.fixed_charge, s.fixed_charge_source) == (D("180"), "override")
    assert s.usable_generation == D("3360.0")


@pytest.mark.parametrize(
    "bad",
    [
        Overrides(usable_generation_pct=D("0")),
        Overrides(usable_generation_pct=D("1.2")),
        Overrides(fixed_charge_monthly=D("-3000")),
        Overrides(savings_rate=D("0")),
        Overrides(savings_rate=D("-2")),
    ],
    ids=["pct-zero", "pct-above-1", "fixed-negative", "rate-zero", "rate-negative"],
)
def test_invalid_overrides_are_rejected_not_ignored(settings, bad):
    """Review fix 2: an override is applied as given or rejected, never silently replaced."""
    from app.services.calc.errors import CalcError

    with pytest.raises(CalcError) as err:
        est(settings, "3", "3200", "340", overrides=bad)
    assert err.value.code == "INVALID_INPUT"


def test_savings_rate_override_wins(settings):
    s = est(settings, "3", "3200", "340", overrides=Overrides(savings_rate=D("7.5")))
    assert s.savings_rate == D("7.5")
    assert s.annual_savings == D("28350")


def test_fixed_charge_at_or_above_bill_is_not_available(settings):
    s = est(settings, "3", "150", "340")
    assert (s.status, s.annual_savings, s.reason) == (
        "not_available",
        None,
        "savings_rate_not_positive",
    )


def test_savings_that_round_to_zero_are_not_available(settings):
    s = est(settings, "1", "3200", "340", overrides=Overrides(savings_rate=D("0.0001")))
    assert (s.status, s.annual_savings, s.reason) == ("not_available", None, "savings_not_positive")


def test_missing_bill_or_units_is_not_available(settings):
    assert est(settings, "3", None, "340").reason == "needs_bill_units"
    assert est(settings, "3", "3200", None).reason == "needs_bill_units"


def test_payback_examples():
    assert payback(D("102000"), D("33909")).years == D("3.0")
    assert payback(D("30000"), D("6000")).years == D("5.0")
    assert payback(D("60000"), D("22606")).years == D("2.7")
    assert payback(D("162000"), D("36600")).years == D("4.4")


def test_payback_rounds_half_up():
    assert payback(D("9000"), D("4000")).years == D("2.3")  # 2.25


@pytest.mark.parametrize("savings", [None, D("0"), D("-10")])
def test_payback_not_available_without_positive_savings(savings):
    p = payback(D("102000"), savings)
    assert (p.years, p.status) == (None, "not_available")


def test_zero_net_cost_is_immediate():
    p = payback(D("0"), D("5000"))
    assert (p.years, p.status) == (D("0"), "immediate")
