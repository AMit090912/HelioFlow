"""Lead qualification when a bill is confirmed (ARCHITECTURE §7, §8).

Runs the M2 engine on *confirmed* values only: the declared roof gives a provisional size (the
final one needs the survey), and the score decides the next action — a Low score swaps the
survey visit for a call and never rejects anyone.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import BillReading, Lead
from app.models.enums import LeadScore, LeadStatus, NextAction
from app.services.calc.scoring import score_lead
from app.services.calc.sizing import recommend
from app.services.rules_repo import load_settings


def _plain(value: object) -> str:
    """Reason values as a person writes them: "650", never "650.00"."""
    try:
        return format(Decimal(str(value)).normalize(), "f")
    except ArithmeticError:
        return str(value)


def qualify_lead(db: Session, lead: Lead, reading: BillReading) -> None:
    settings = load_settings(db)  # raises CalcError(SETTINGS_*) if business settings are broken
    sizing = recommend(
        ownership=lead.ownership.value,
        avg_monthly_units=reading.avg_monthly_units,
        declared_roof_sqft=lead.roof_area_sqft,
        verified_roof_sqft=lead.verified_roof_area_sqft,
        sanctioned_load_kw=reading.sanctioned_load_kw,
        settings=settings,
    )
    score = score_lead(lead.ownership.value, reading.bill_amount, "confirmed", sizing, settings)
    lead.score = LeadScore(score.score)
    lead.score_reasons = [
        {k: (v if k in ("code", "source") else _plain(v)) for k, v in reason.items()}
        for reason in score.reasons
    ]
    lead.recommended_kw = sizing.recommended_kw
    lead.sizing_detail = {
        "status": sizing.status,
        "roof_basis": sizing.roof_basis,
        "annual_units": _plain(sizing.annual_units),
        "required_kw_exact": str(sizing.required_kw),
        "kw_by_usage": _plain(sizing.kw_by_usage),
        "kw_by_roof": None if sizing.kw_by_roof is None else _plain(sizing.kw_by_roof),
        "flags": list(sizing.flags),
        "settings_used": {
            "generation_kwh_per_kw_year": _plain(settings.generation_kwh_per_kw_year),
            "roof_sqft_per_kw": _plain(settings.roof_sqft_per_kw),
            "min_monthly_bill_for_survey": _plain(settings.min_monthly_bill_for_survey),
        },
    }
    lead.next_action = NextAction(score.next_action)
    lead.status = (
        LeadStatus.survey_pending
        if score.next_action == "survey_visit"
        else LeadStatus.call_pending
    )
