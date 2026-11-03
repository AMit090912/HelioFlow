"""Quotes: live preview, immutable snapshot at send, supersede and accept (§3.8, §8, §10, §11).

The engine (`build_quote_options`) is pure; this module gathers its inputs from the database,
freezes the result into a JSON snapshot (rule rows copied in, every number as a plain string),
and runs the lifecycle transitions. Quote views are rendered from the snapshot only.
"""

import uuid
from dataclasses import asdict, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import BillReading, Lead, Quote, User
from app.models.enums import LeadStatus, QuoteStatus
from app.schemas.quotes import OverrideIn, QuoteView
from app.services import notify
from app.services.calc.engine import OptionQuote, QuoteInputs, QuoteOptions, build_quote_options
from app.services.calc.errors import CalcError
from app.services.calc.savings import Overrides, estimate_savings
from app.services.calc.sizing import kw_by_roof
from app.services.calc.types import PriceRule, Settings, SubsidyRule
from app.services.lead_actions import effective_sanctioned_load, lock_lead, log_event
from app.services.rules_repo import load_price_rules, load_settings, load_subsidy_rules

INDIA = ZoneInfo("Asia/Kolkata")
QUOTABLE = {
    LeadStatus.survey_pending,
    LeadStatus.call_pending,
    LeadStatus.surveyed,
    LeadStatus.quoted,
}


def today_in_india() -> date:
    """`priced_on` is the quote's date in India (A-20), not the server's UTC date."""
    return datetime.now(INDIA).date()


def s(value: Any) -> Any:
    """JSON-safe, human-shaped numbers: Decimal("340.00") → "340"; dates → ISO."""
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [s(v) for v in value]
    if isinstance(value, dict):
        return {k: s(v) for k, v in value.items()}
    return value


def calc_error(exc: CalcError) -> ApiError:
    return ApiError(422, exc.code, exc.message)


# --- Inputs ---


def _reading(db: Session, lead: Lead) -> BillReading:
    if lead.current_bill_reading_id is None:
        raise ApiError(422, "BILL_NOT_CONFIRMED", "The homeowner hasn't confirmed a bill yet.")
    return db.get(BillReading, lead.current_bill_reading_id)


def _overrides(items: list[OverrideIn]) -> Overrides:
    fields = [o.field for o in items]
    if len(fields) != len(set(fields)):
        raise ApiError(422, "OVERRIDE_DUPLICATE", "Each value can be overridden once.")
    return Overrides(**{o.field: o.value for o in items})


def _inputs(db: Session, lead: Lead) -> tuple[QuoteInputs, BillReading, str | None]:
    reading = _reading(db, lead)
    load, load_source = effective_sanctioned_load(db, lead)
    inputs = QuoteInputs(
        ownership=lead.ownership.value,
        property_type=lead.property_type.value,
        avg_monthly_units=reading.avg_monthly_units,
        monthly_bill=reading.bill_amount or lead.declared_monthly_bill,
        declared_roof_sqft=lead.roof_area_sqft,
        verified_roof_sqft=lead.verified_roof_area_sqft,
        sanctioned_load_kw=load,
        bill_fixed_charge=reading.fixed_charge_monthly,
    )
    return inputs, reading, load_source


def _check_quotable(lead: Lead) -> None:
    if lead.status not in QUOTABLE:
        raise ApiError(
            409,
            "LEAD_STATUS_CONFLICT",
            f"A quote can't be built while the lead is {lead.status.value}.",
        )


def preview(
    db: Session, lead: Lead, overrides: list[OverrideIn], on: date
) -> tuple[QuoteOptions, BillReading, str | None]:
    _check_quotable(lead)
    inputs, reading, load_source = _inputs(db, lead)
    try:
        result = build_quote_options(
            inputs=inputs,
            price_rules=load_price_rules(db),
            subsidy_rules=load_subsidy_rules(db),
            settings=load_settings(db),
            on=on,
            overrides=_overrides(overrides),
        )
    except CalcError as exc:
        raise calc_error(exc) from exc
    return result, reading, load_source


# --- Snapshot ---


def _option(q: OptionQuote) -> dict[str, Any]:
    sv = q.savings
    out = s(
        {
            "kw": q.kw,
            "recommended": q.recommended,
            "gross": q.gross,
            "subsidy": {
                "status": q.subsidy.status,
                "amount": q.subsidy.amount,
                "raw": q.subsidy.raw,
                "capped": q.subsidy.capped,
            },
            "net": q.net,
            "savings": {
                "annual_generation": sv.annual_generation,
                "usable_generation": sv.usable_generation,
                "usable_generation_pct": sv.usable_generation_pct,
                "fixed_charge": sv.fixed_charge,
                "fixed_charge_source": sv.fixed_charge_source,
                "savings_rate": sv.savings_rate,
                "annual_savings": sv.annual_savings,
                "status": sv.status,
                "reason": sv.reason,
            },
            "payback": {"years": None, "status": q.payback.status},
            "price_rule_id": q.price_rule.id,
            "flags": list(q.flags),
        }
    )
    # Payback is defined to 0.1 year (§10): keep "3.0", don't normalise it to "3".
    if q.payback.years is not None:
        out["payback"]["years"] = format(q.payback.years, "f")
    return out


def _price_rule(rule: PriceRule) -> dict[str, Any]:
    return s(asdict(rule))


def _subsidy_rule(rule: SubsidyRule | None) -> dict[str, Any] | None:
    return None if rule is None else s(asdict(rule))


def _settings(settings: Settings) -> dict[str, Any]:
    return s(asdict(settings))


def _natural_value(result: QuoteOptions, field: str) -> Decimal | None:
    """What a field would have been without its override (the override's "from")."""
    if field == "usable_generation_pct":
        return result.settings.usable_generation_pct
    inputs = result.inputs
    if field == "fixed_charge_monthly":
        if inputs.bill_fixed_charge is not None:  # ₹0 on the bill is a real value
            return inputs.bill_fixed_charge
        return result.settings.default_fixed_charge_monthly
    without = replace(result.overrides, savings_rate=None)
    natural = estimate_savings(
        kw=result.recommended_kw,
        avg_monthly_units=inputs.avg_monthly_units,
        monthly_bill=inputs.monthly_bill,
        bill_fixed_charge=inputs.bill_fixed_charge,
        settings=result.settings,
        overrides=without,
    )
    rate = natural.savings_rate
    # Recorded for people to read: ₹/kWh to 4 places (the engine keeps full precision).
    return None if rate is None else rate.quantize(Decimal("0.0001"))


def overrides_record(
    result: QuoteOptions, items: list[OverrideIn], actor_id: uuid.UUID | None
) -> list[dict[str, Any]]:
    return [
        s(
            {
                "field": o.field,
                "from": _natural_value(result, o.field),
                "to": o.value,
                "by": str(actor_id) if actor_id else None,
                "reason": (o.reason or "").strip() or None,
            }
        )
        for o in items
    ]


def options_payload(result: QuoteOptions) -> dict[str, Any]:
    """The parts of a snapshot the builder preview also shows."""
    return {
        "recommended_kw": s(result.recommended_kw),
        "max_allowed_kw": s(result.options.max_allowed_kw),
        "removed": [dict(r) for r in result.options.removed],
        "options": [_option(q) for q in result.quotes],
    }


def snapshot_of(
    result: QuoteOptions,
    *,
    lead: Lead,
    reading: BillReading,
    overrides: list[OverrideIn],
    actor_id: uuid.UUID,
    sanctioned_load_source: str | None,
) -> dict[str, Any]:
    inputs = result.inputs
    sizing = result.sizing
    subsidy_rules = {q.subsidy.rule.id: q.subsidy.rule for q in result.quotes if q.subsidy.rule}
    price_rules = {q.price_rule.id: q.price_rule for q in result.quotes}
    return {
        "calc_version": result.calc_version,
        "priced_on": s(result.priced_on),
        "inputs": s(
            {
                **asdict(inputs),
                "segment": "residential" if inputs.property_type == "home" else "business",
                "sanctioned_load_source": sanctioned_load_source,
                "bill_reading_id": str(reading.id),
                "provisional_kw": lead.recommended_kw,
            }
        ),
        "settings": _settings(result.settings),
        "price_rules_used": [_price_rule(r) for r in price_rules.values()],
        "subsidy_rule": _subsidy_rule(next(iter(subsidy_rules.values()), None)),
        "overrides": overrides_record(result, overrides, actor_id),
        "assumptions": list(result.assumptions),
        "sizing": s(
            {
                "final_kw": sizing.recommended_kw,
                "status": sizing.status,
                "roof_basis": sizing.roof_basis,
                "annual_units": sizing.annual_units,
                "required_kw_exact": sizing.required_kw,
                "kw_by_usage": sizing.kw_by_usage,
                "kw_by_roof": sizing.kw_by_roof,
                "flags": list(sizing.flags),
            }
        ),
        **options_payload(result),
    }


# --- Lifecycle ---


def send_quote(db: Session, lead_id: uuid.UUID, actor: User, overrides: list[OverrideIn]) -> Quote:
    lead = lock_lead(db, lead_id)
    for o in overrides:
        if len(" ".join((o.reason or "").split())) < 5:
            raise ApiError(
                422, "OVERRIDE_REASON_REQUIRED", "Give a reason for each override before sending."
            )
    on = today_in_india()
    result, reading, load_source = preview(db, lead, overrides, on)
    snapshot = snapshot_of(
        result,
        lead=lead,
        reading=reading,
        overrides=overrides,
        actor_id=actor.id,
        sanctioned_load_source=load_source,
    )
    now = datetime.now(UTC)
    seq = db.execute(text("SELECT nextval('quote_number_seq')")).scalar_one()

    # One open quote per lead (partial unique index): retire the old one before inserting,
    # then point it at its replacement once that row exists (FK).
    old = db.execute(
        select(Quote)
        .where(Quote.lead_id == lead.id, Quote.status == QuoteStatus.sent)
        .with_for_update()
    ).scalar_one_or_none()
    if old is not None:
        old.status, old.superseded_at = QuoteStatus.superseded, now
        db.flush()
    quote = Quote(
        number=f"HF-Q-{on.year}-{seq:06d}",
        lead_id=lead.id,
        priced_on=on,
        snapshot=snapshot,
        calc_version=result.calc_version,
        created_by=actor.id,
        sent_at=now,
        status=QuoteStatus.sent,
    )
    db.add(quote)
    db.flush()
    if old is not None:
        old.superseded_by_quote_id = quote.id
    log_event(db, lead, actor, "quote_sent", to_status=LeadStatus.quoted, note=quote.number)
    notify.quote_sent(db, lead, quote)
    db.flush()
    return quote


def _check_still_fits(db: Session, lead: Lead, kw: Decimal) -> None:
    """§8: a size above the verified roof or sanctioned load is never offered. Staff may re-check
    the roof after quoting; a size that no longer fits is refused until a revised quote is sent."""
    roof = lead.verified_roof_area_sqft
    roof_kw = kw_by_roof(roof, load_settings(db)) if roof is not None else None
    load, _ = effective_sanctioned_load(db, lead)
    if roof_kw is None or kw > roof_kw or (load is not None and kw > load):
        raise ApiError(
            409,
            "QUOTE_OUTDATED",
            "Our roof check changed after this quote. We'll send you a revised quote.",
        )


def accept_quote(db: Session, quote_id: uuid.UUID, homeowner: User, selected_kw: Decimal) -> Quote:
    quote = db.get(Quote, quote_id)
    if quote is None:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    lead = lock_lead(db, quote.lead_id)
    if lead.homeowner_id != homeowner.id:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    db.refresh(quote, with_for_update=True)
    if quote.status == QuoteStatus.superseded:
        raise ApiError(409, "QUOTE_SUPERSEDED", "This quote was replaced by a newer one.")
    if quote.status == QuoteStatus.accepted:
        raise ApiError(409, "QUOTE_ALREADY_ACCEPTED", "This quote is already accepted.")
    offered = {Decimal(o["kw"]) for o in quote.snapshot["options"]}
    if selected_kw not in offered:
        raise ApiError(422, "OPTION_NOT_OFFERED", "Choose one of the sizes in this quote.")
    if lead.status != LeadStatus.quoted:
        raise ApiError(409, "LEAD_STATUS_CONFLICT", "This quote can no longer be accepted.")
    _check_still_fits(db, lead, selected_kw)
    quote.status = QuoteStatus.accepted
    quote.selected_kw = selected_kw
    quote.accepted_at = datetime.now(UTC)
    quote.accepted_by = homeowner.id
    log_event(
        db,
        lead,
        homeowner,
        "quote_accepted",
        to_status=LeadStatus.accepted,
        note=f"{quote.number}: {s(selected_kw)} kW",
    )
    db.flush()
    return quote


# --- Reading ---


def homeowner_view(view: QuoteView) -> QuoteView:
    """What a homeowner sees: which values sales adjusted, not who did it or their notes."""
    public = [{k: o.get(k) for k in ("field", "from", "to")} for o in view.overrides]
    return view.model_copy(update={"overrides": public})


def view_of(quote: Quote, lead: Lead, db: Session | None = None) -> QuoteView:
    """Pass `db` to resolve `latest_quote_id` for a replaced quote."""
    snap = quote.snapshot
    latest = None
    if db is not None and quote.status == QuoteStatus.superseded:
        newest = current_quote(db, lead.id)
        latest = newest.id if newest is not None else None
    return QuoteView(
        id=quote.id,
        number=quote.number,
        status=quote.status.value,
        lead_id=lead.id,
        lead_code=lead.code,
        lead_status=lead.status.value,
        sent_at=quote.sent_at,
        priced_on=quote.priced_on,
        selected_kw=quote.selected_kw,
        accepted_at=quote.accepted_at,
        superseded_by_quote_id=quote.superseded_by_quote_id,
        latest_quote_id=latest,
        recommended_kw=snap["recommended_kw"],
        options=snap["options"],
        removed=snap["removed"],
        assumptions=snap["assumptions"],
        overrides=snap["overrides"],
        subsidy_rule=snap["subsidy_rule"],
        inputs=snap["inputs"],
    )


def current_quote(db: Session, lead_id: uuid.UUID) -> Quote | None:
    """The newest quote that hasn't been replaced (sent or accepted)."""
    return db.execute(
        select(Quote)
        .where(Quote.lead_id == lead_id, Quote.status != QuoteStatus.superseded)
        .order_by(Quote.sent_at.desc())
        .limit(1)
    ).scalar_one_or_none()
