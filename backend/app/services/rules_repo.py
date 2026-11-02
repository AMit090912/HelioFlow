"""The only DB-aware part of the calculation path: ORM rows → validated engine dataclasses."""

from decimal import Decimal, InvalidOperation

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PriceRule as PriceRuleRow
from app.models import Setting
from app.models import SubsidyRule as SubsidyRuleRow
from app.schemas.settings import REQUIRED_KEYS, BusinessSettings
from app.services.calc.errors import CalcError
from app.services.calc.types import PriceRule, Settings, SubsidyRule, SubsidySlab


def load_settings(db: Session) -> Settings:
    rows = {row.key: row.value for row in db.execute(select(Setting)).scalars()}
    missing = sorted(REQUIRED_KEYS - rows.keys())
    if missing:
        raise CalcError(
            "SETTINGS_INCOMPLETE", "Some business settings are missing.", missing=missing
        )
    try:
        valid = BusinessSettings.model_validate(rows)
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})
        raise CalcError(
            "SETTINGS_INVALID", "Some business settings are invalid.", fields=fields
        ) from exc
    return Settings(
        generation_kwh_per_kw_year=valid.generation_kwh_per_kw_year,
        roof_sqft_per_kw=valid.roof_sqft_per_kw,
        min_monthly_bill_for_survey=valid.min_monthly_bill_for_survey,
        capacity_options_kw=tuple(valid.capacity_options_kw),
        usable_generation_pct=valid.usable_generation_pct,
        default_fixed_charge_monthly=valid.default_fixed_charge_monthly,
        quote_option_offsets=tuple(valid.quote_option_offsets),
    )


def load_price_rules(db: Session) -> tuple[PriceRule, ...]:
    rows = db.execute(select(PriceRuleRow).order_by(PriceRuleRow.effective_from)).scalars()
    return tuple(
        PriceRule(
            id=str(r.id),
            min_kw=r.min_kw,
            max_kw=r.max_kw,
            price_per_kw=r.price_per_kw,
            gst_inclusive=r.gst_inclusive,
            effective_from=r.effective_from,
            effective_to=r.effective_to,
        )
        for r in rows
    )


def _slabs(rule_id: str, raw: object) -> tuple[SubsidySlab, ...]:
    """Slabs: non-empty, start at 0 kW, contiguous, non-negative amounts."""

    def bad(why: str) -> CalcError:
        return CalcError("INVALID_RULE", f"Subsidy rule slabs are invalid: {why}.", rule_id=rule_id)

    if not isinstance(raw, list) or not raw:
        raise bad("no slabs")
    slabs: list[SubsidySlab] = []
    expected_from = Decimal("0")
    for item in raw:
        try:
            slab = SubsidySlab(
                Decimal(str(item["from_kw"])),
                Decimal(str(item["to_kw"])),
                Decimal(str(item["amount_per_kw"])),
            )
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise bad("malformed slab") from exc
        if slab.from_kw != expected_from:
            raise bad(f"gap or overlap at {slab.from_kw} kW")
        if slab.to_kw <= slab.from_kw or slab.amount_per_kw < 0:
            raise bad("empty slab or negative amount")
        slabs.append(slab)
        expected_from = slab.to_kw
    return tuple(slabs)


def load_subsidy_rules(db: Session) -> tuple[SubsidyRule, ...]:
    rows = db.execute(select(SubsidyRuleRow).order_by(SubsidyRuleRow.effective_from)).scalars()
    return tuple(
        SubsidyRule(
            id=str(r.id),
            scheme_code=r.scheme_code,
            segment=r.segment.value,
            slabs=_slabs(str(r.id), r.slabs),
            cap_amount=r.cap_amount,
            effective_from=r.effective_from,
            effective_to=r.effective_to,
            source_note=r.source_note,
        )
        for r in rows
    )
