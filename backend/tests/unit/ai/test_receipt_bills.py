"""Receipt-style Indian spot bills (e.g. TSSPDCL "bill-cum-notice"): multi-month periods, meter
readings, arrears, customer charges, foreign bills, and nulls from providers (§6.1, §6.3)."""

from decimal import Decimal as D

from app.services.ai import BillExtraction, sanity_flags
from app.services.ai.validation import monthly_figures, suggested_average_units

# Values printed on the user's sample TSSPDCL bill (93-day period, Malkajgiri).
SPOT_93_DAYS = {
    "is_electricity_bill": True,
    "is_indian_bill": True,
    "legibility": "fair",
    "consumer_number": {"value": None, "confidence": 0},  # masked on the photo
    "tariff_category": {"value": "1B(ii) DOMESTIC", "confidence": 0.95},
    "sanctioned_load_kw": {"value": 1.0, "confidence": 0.95},
    "billing_days": {"value": 93, "confidence": 0.95},
    "previous_reading": {"value": 1934, "confidence": 0.9},
    "present_reading": {"value": 3671, "confidence": 0.9},
    "meter_multiplier": {"value": 1.0, "confidence": 0.9},
    "current_units": {"value": 1737, "confidence": 0.95},
    "bill_amount": {"value": 12877.84, "confidence": 0.9},
    "arrears": {"value": 5586.0, "confidence": 0.9},
    "total_due": {"value": 12907.0, "confidence": 0.9},
    "fixed_charge": {"value": 240.0, "confidence": 0.8},
}


def spot(**overrides) -> BillExtraction:
    return BillExtraction.model_validate({**SPOT_93_DAYS, **overrides})


# --- Schema ---


def test_providers_may_write_null_for_a_whole_field():
    """Gemini sometimes answers "bill_amount": null instead of {"value": null}: same meaning."""
    e = BillExtraction.model_validate(
        {
            "is_electricity_bill": True,
            "legibility": "good",
            "monthly_units": None,
            "bill_amount": None,
            "fixed_charge": None,
            "current_units": {"value": 196, "confidence": 1},
        }
    )
    assert e.bill_amount.value is None and e.monthly_units.value is None
    assert e.current_units.value == 196 and e.is_indian_bill is None


def test_older_readings_without_new_fields_still_parse():
    old = {k: v for k, v in SPOT_93_DAYS.items() if k in ("is_electricity_bill", "legibility")}
    e = BillExtraction.model_validate({**old, "current_units": {"value": 340, "confidence": 1}})
    assert e.billing_days.value is None and e.arrears.value is None


# --- Monthly figures ---


def test_a_93_day_bill_becomes_per_month_figures():
    m = monthly_figures(spot())
    assert m.billing_days == 93
    assert m.method == "period_normalised"
    assert m.avg_monthly_units == D("568.10")  # 1737 × (365/12) ÷ 93
    assert m.bill_amount == D("4211.84")  # 12877.84 × 30.4167 ÷ 93
    assert m.fixed_charge == D("78.49")  # 240 × 30.4167 ÷ 93


def test_a_normal_month_is_left_alone():
    m = monthly_figures(spot(billing_days={"value": 30, "confidence": 1}))
    assert (m.avg_monthly_units, m.method) == (D("1737"), "current_month")
    assert m.bill_amount == D("12877.84") and m.fixed_charge == D("240")


def test_unknown_period_is_treated_as_one_month():
    m = monthly_figures(spot(billing_days={"value": None, "confidence": 0}))
    assert m.method == "current_month" and m.billing_days is None


def test_history_still_wins_when_three_months_are_printed():
    months = [{"month": f"2026-0{i}", "units": u} for i, u in [(7, 500), (8, 600), (9, 700)]]
    m = monthly_figures(spot(monthly_units={"value": months, "confidence": 0.9}))
    assert (m.avg_monthly_units, m.method) == (D("600.00"), "history_mean")
    assert m.bill_amount == D("4211.84")  # the bill is still this period's, made monthly


def test_units_come_from_meter_readings_when_not_printed():
    m = monthly_figures(
        spot(
            current_units={"value": None, "confidence": 0},
            billing_days={"value": 31, "confidence": 1},
        )
    )
    assert (m.avg_monthly_units, m.method) == (D("1737"), "meter_readings")


def test_meter_multiplier_applies_to_readings():
    m = monthly_figures(
        spot(
            current_units={"value": None, "confidence": 0},
            billing_days={"value": 30, "confidence": 1},
            previous_reading={"value": 100, "confidence": 1},
            present_reading={"value": 150, "confidence": 1},
            meter_multiplier={"value": 2, "confidence": 1},
        )
    )
    assert m.avg_monthly_units == D("100")


def test_legacy_helper_still_answers():
    assert suggested_average_units(spot()) == (D("568.10"), "period_normalised")


# --- Sanity flags ---


def test_spot_bill_reads_clean():
    assert sanity_flags(spot(), declared_bill=D("4000")) == {
        "current_units": ["long_billing_period"]
    }


def test_units_that_disagree_with_meter_readings_are_flagged():
    flags = sanity_flags(spot(current_units={"value": 1500, "confidence": 0.9}), declared_bill=None)
    assert "units_mismatch_readings" in flags["current_units"]


def test_total_due_read_as_the_bill_is_flagged():
    flags = sanity_flags(
        spot(bill_amount={"value": 12907.0, "confidence": 0.9}), declared_bill=None
    )
    assert "may_include_arrears" in flags["bill_amount"]


def test_declared_bill_is_compared_per_month():
    """The homeowner types a monthly bill; a 93-day bill's total is not compared to it."""
    flags = sanity_flags(spot(), declared_bill=D("4200"))
    assert "differs_from_declared" not in flags.get("bill_amount", [])


def test_masked_consumer_number_is_unusual():
    flags = sanity_flags(
        spot(consumer_number={"value": "000000000000", "confidence": 0.9}), declared_bill=None
    )
    assert "format_unusual" in flags["consumer_number"]


def test_foreign_bill_is_flagged_for_reupload():
    flags = sanity_flags(spot(is_indian_bill=False), declared_bill=None)
    assert "not_indian_bill" in flags["document"]
