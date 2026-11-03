"""Receipt-style Indian spot bills (e.g. TSSPDCL "bill-cum-notice"): multi-month periods, meter
readings, arrears, customer charges, and nulls from providers (§6.1, §6.3)."""

from decimal import Decimal as D

from app.services.ai import BillExtraction, sanity_flags
from app.services.ai.validation import monthly_figures, suggested_average_units

# Values printed on the user's sample TSSPDCL bill (93-day period, Malkajgiri).
SPOT_93_DAYS = {
    "is_electricity_bill": True,
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
    assert e.current_units.value == 196


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


# --- Quarterly bill paid in instalments (user sample: readings 22/04/24 → 22/07/24) ---

QUARTERLY = {
    "is_electricity_bill": True,
    "legibility": "fair",
    "previous_reading": {"value": 10528, "confidence": 0.95},
    "present_reading": {"value": 14063, "confidence": 0.95},
    "previous_reading_date": {"value": "2024-04-22", "confidence": 0.9},
    "present_reading_date": {"value": "2024-07-22", "confidence": 0.9},
    "current_units": {"value": 3535, "confidence": 0.95},
    "bill_amount": {"value": 11196, "confidence": 0.9},  # one of three monthly instalments
    "arrears": {"value": 0, "confidence": 1},
    "total_due": {"value": 33234, "confidence": 0.9},
}


def quarterly(**overrides) -> BillExtraction:
    return BillExtraction.model_validate({**QUARTERLY, **overrides})


def test_period_comes_from_reading_dates_when_days_are_not_printed():
    m = monthly_figures(quarterly())
    assert m.billing_days == 91
    assert m.avg_monthly_units == D("1181.57")  # 3535 × (365/12) ÷ 91


def test_printed_days_win_over_dates():
    assert (
        monthly_figures(quarterly(billing_days={"value": 92, "confidence": 1})).billing_days == 92
    )


def test_unreadable_dates_are_ignored():
    m = monthly_figures(quarterly(present_reading_date={"value": "22/07/24", "confidence": 0.9}))
    assert m.billing_days is None


def test_meter_readings_win_when_printed_units_disagree():
    """Gemini misread 3535 as 3595; the two readings it also read give 3535."""
    m = monthly_figures(quarterly(current_units={"value": 3595, "confidence": 1}))
    assert m.method == "meter_readings"
    assert m.avg_monthly_units == D("1181.57")
    flags = sanity_flags(quarterly(current_units={"value": 3595, "confidence": 1}), None)
    assert "units_mismatch_readings" in flags["current_units"]


def test_one_instalment_is_replaced_by_the_period_total():
    m = monthly_figures(quarterly())
    assert m.bill_amount == D("11108.43")  # 33234 (no arrears) × (365/12) ÷ 91
    flags = sanity_flags(quarterly(), declared_bill=None)
    assert "bill_amount_partial" in flags["bill_amount"]


def test_period_total_is_kept_when_already_read():
    m = monthly_figures(quarterly(bill_amount={"value": 33587.5, "confidence": 0.9}))
    assert m.bill_amount == D("11226.59")
    assert "bill_amount_partial" not in sanity_flags(
        quarterly(bill_amount={"value": 33587.5, "confidence": 0.9}), None
    ).get("bill_amount", [])


# --- Demo mode never answers for a real bill ---


def test_demo_mode_sends_real_bills_to_the_live_chain_or_manual_entry():
    from app.core.config import Settings
    from app.main import providers_for
    from app.services.ai.demo import SAMPLE_FINGERPRINTS, DemoProvider

    sample = next(iter(SAMPLE_FINGERPRINTS))
    with_keys = providers_for(Settings(ai_mode="demo", groq_api_key="k", gemini_api_key=""))
    assert [type(p) for p in with_keys(sample)] == [DemoProvider]
    assert [p.name for p in with_keys("f" * 64)] == ["groq"]
    no_keys = providers_for(Settings(ai_mode="demo", groq_api_key="", gemini_api_key=""))
    assert no_keys("f" * 64) == []  # → manual entry, not "this isn't a bill"


def test_instalments_recognised_without_arrears_when_months_match():
    """Groq read total 32933 and one instalment 11196 but no arrears line: 3 months, ×2.94."""
    e = quarterly(
        arrears={"value": None, "confidence": 0}, total_due={"value": 32933, "confidence": 0.9}
    )
    assert monthly_figures(e).bill_amount == D("11007.83")  # 32933 × (365/12) ÷ 91
    assert "bill_amount_partial" in sanity_flags(e, None)["bill_amount"]


def test_unknown_arrears_with_no_matching_period_keeps_the_bill():
    """Total ≈ 3× the bill on a ONE-month bill is more likely arrears than instalments."""
    e = quarterly(
        arrears={"value": None, "confidence": 0},
        total_due={"value": 32933, "confidence": 0.9},
        previous_reading_date={"value": "2024-06-22", "confidence": 0.9},
    )
    assert monthly_figures(e).bill_amount == D("11196")


def test_one_month_amount_on_a_quarterly_bill_is_used_as_the_month():
    """Groq's second reading: total_due also 11196 (first due-date row). ₹11196 over 3 months of
    1,182 units/month would be ₹3.17/unit — too cheap for that use; ₹9.47/unit for one month."""
    e = quarterly(total_due={"value": 11196, "confidence": 0.9})
    m = monthly_figures(e)
    assert m.bill_amount == D("11196")
    assert "bill_amount_partial" in sanity_flags(e, None)["bill_amount"]


def test_low_use_long_bill_is_not_reinterpreted():
    """A cheap bill for low use (e.g. a subsidised first slab) is left alone."""
    e = quarterly(
        present_reading={"value": 10828, "confidence": 1},
        current_units={"value": 300, "confidence": 1},  # 100 units/month
        bill_amount={"value": 600, "confidence": 1},
        total_due={"value": 600, "confidence": 1},
    )
    assert monthly_figures(e).bill_amount == D("200.55")  # 600 × (365/12) ÷ 91
