"""Screen 9: dated price and subsidy rules, and business settings (§3.5–3.7, §9.3).

Sales may read; only admin may write (§4, Q-7). Overlapping rule dates are refused by the
database's EXCLUDE constraints and reported as 409 RULE_OVERLAP — never as a 500. Rules are
never deleted: a rule ends by setting `effective_to`, so history stays explainable (and every
sent quote carries its own copy anyway, §11).
"""

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_roles
from app.core.errors import ApiError
from app.models import PriceRule, Setting, SubsidyRule, User
from app.models.enums import SubsidySegment
from app.schemas.bills import plain
from app.schemas.rules import (
    CloseIn,
    PriceRuleIn,
    PriceRuleOut,
    SettingIn,
    SubsidyRuleIn,
    SubsidyRuleOut,
)
from app.schemas.settings import REQUIRED_KEYS, BusinessSettings

router = APIRouter(prefix="/rules", tags=["rules"])
readers = require_roles("sales", "admin")
admin_only = require_roles("admin")

EXCLUSION_VIOLATION = "23P01"
CHECK_VIOLATION = "23514"


FAR_FUTURE = date(9999, 12, 31)


def _span(rule_from: date, rule_to: date | None) -> str:
    return f"from {rule_from.isoformat()} ({rule_to.isoformat() if rule_to else 'open-ended'})"


def _price_conflicts(
    db: Session, min_kw: Decimal, max_kw: Decimal, start: date, end: date | None, skip=None
) -> list[PriceRule]:
    """Rules the database refused us for: kW range and dates both overlap (inclusive, §3.5)."""
    query = select(PriceRule).where(
        PriceRule.min_kw <= max_kw,
        PriceRule.max_kw >= min_kw,
        PriceRule.effective_from <= (end or FAR_FUTURE),
        func.coalesce(PriceRule.effective_to, FAR_FUTURE) >= start,
    )
    if skip is not None:
        query = query.where(PriceRule.id != skip)
    return list(db.execute(query).scalars())


def _subsidy_conflicts(
    db: Session, scheme: str, start: date, end: date | None, skip=None
) -> list[SubsidyRule]:
    query = select(SubsidyRule).where(
        SubsidyRule.scheme_code == scheme,
        SubsidyRule.effective_from <= (end or FAR_FUTURE),
        func.coalesce(SubsidyRule.effective_to, FAR_FUTURE) >= start,
    )
    if skip is not None:
        query = query.where(SubsidyRule.id != skip)
    return list(db.execute(query).scalars())


def _overlap_error(conflicts: Callable[[], list], describe: Callable[[Any], str]) -> ApiError:
    rows = conflicts()
    if not rows:
        return ApiError(409, "RULE_OVERLAP", "These dates overlap another rule.")
    first = rows[0]
    details = [
        {
            "id": str(r.id),
            "effective_from": r.effective_from.isoformat(),
            "effective_to": r.effective_to.isoformat() if r.effective_to else None,
            **(
                {"min_kw": plain(r.min_kw), "max_kw": plain(r.max_kw)}
                if isinstance(r, PriceRule)
                else {"scheme_code": r.scheme_code}
            ),
        }
        for r in rows
    ]
    return ApiError(409, "RULE_OVERLAP", describe(first), details)


def _save(db: Session, on_overlap: Callable[[], ApiError]) -> None:
    """Commit, translating constraint failures into answers a person can act on."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        state = getattr(exc.orig, "sqlstate", None)
        if state == EXCLUSION_VIOLATION:
            raise on_overlap() from exc
        if state == CHECK_VIOLATION:
            raise ApiError(
                422, "RULE_INVALID", "The end date must be on or after the start."
            ) from exc
        raise


def _describe_price(r: PriceRule) -> str:
    return (
        f"The kW range and dates overlap the rule for {plain(r.min_kw)}–{plain(r.max_kw)} kW "
        f"{_span(r.effective_from, r.effective_to)}. End that rule first, or pick another "
        "kW range or dates."
    )


def _describe_subsidy(r: SubsidyRule) -> str:
    return (
        f"These dates overlap the {r.scheme_code} rule {_span(r.effective_from, r.effective_to)}. "
        "End that rule first, or pick other dates."
    )


def _price_out(rule: PriceRule) -> PriceRuleOut:
    return PriceRuleOut.model_validate(rule, from_attributes=True)


def _subsidy_out(rule: SubsidyRule) -> SubsidyRuleOut:
    slabs = [{k: plain(Decimal(str(v))) for k, v in slab.items()} for slab in rule.slabs]
    return SubsidyRuleOut(
        id=rule.id,
        scheme_code=rule.scheme_code,
        segment=rule.segment.value,
        slabs=slabs,
        cap_amount=rule.cap_amount,
        effective_from=rule.effective_from,
        effective_to=rule.effective_to,
        source_note=rule.source_note,
    )


# --- Price rules ---


@router.get("/price", response_model=list[PriceRuleOut])
def list_price_rules(db: Session = Depends(get_db), _: User = Depends(readers)):
    rows = db.execute(select(PriceRule).order_by(PriceRule.effective_from, PriceRule.min_kw))
    return [_price_out(r) for r in rows.scalars()]


@router.post("/price", response_model=PriceRuleOut, status_code=201)
def create_price_rule(
    body: PriceRuleIn, db: Session = Depends(get_db), user: User = Depends(admin_only)
):
    if not body.gst_inclusive:
        # No GST rate is configured, so the calculator refuses ex-GST prices (A-11).
        raise ApiError(422, "GST_EXCLUSIVE", "Prices must include GST.")
    rule = PriceRule(**body.model_dump(), created_by=user.id)
    db.add(rule)
    _save(
        db,
        lambda: _overlap_error(
            lambda: _price_conflicts(
                db, body.min_kw, body.max_kw, body.effective_from, body.effective_to
            ),
            _describe_price,
        ),
    )
    return _price_out(rule)


@router.patch("/price/{rule_id}", response_model=PriceRuleOut)
def close_price_rule(
    rule_id: uuid.UUID, body: CloseIn, db: Session = Depends(get_db), _: User = Depends(admin_only)
):
    rule = db.get(PriceRule, rule_id)
    if rule is None:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    lo, hi, start = rule.min_kw, rule.max_kw, rule.effective_from  # read before a rollback
    rule.effective_to = body.effective_to
    _save(
        db,
        lambda: _overlap_error(
            lambda: _price_conflicts(db, lo, hi, start, body.effective_to, skip=rule_id),
            _describe_price,
        ),
    )
    return _price_out(rule)


# --- Subsidy rules ---


@router.get("/subsidy", response_model=list[SubsidyRuleOut])
def list_subsidy_rules(db: Session = Depends(get_db), _: User = Depends(readers)):
    rows = db.execute(select(SubsidyRule).order_by(SubsidyRule.effective_from))
    return [_subsidy_out(r) for r in rows.scalars()]


@router.post("/subsidy", response_model=SubsidyRuleOut, status_code=201)
def create_subsidy_rule(
    body: SubsidyRuleIn, db: Session = Depends(get_db), user: User = Depends(admin_only)
):
    data = body.model_dump()
    slabs = [{k: str(v) for k, v in slab.items()} for slab in data.pop("slabs")]
    rule = SubsidyRule(
        **{**data, "segment": SubsidySegment(body.segment)}, slabs=slabs, created_by=user.id
    )
    db.add(rule)
    _save(
        db,
        lambda: _overlap_error(
            lambda: _subsidy_conflicts(
                db, body.scheme_code, body.effective_from, body.effective_to
            ),
            _describe_subsidy,
        ),
    )
    return _subsidy_out(rule)


@router.patch("/subsidy/{rule_id}", response_model=SubsidyRuleOut)
def close_subsidy_rule(
    rule_id: uuid.UUID, body: CloseIn, db: Session = Depends(get_db), _: User = Depends(admin_only)
):
    rule = db.get(SubsidyRule, rule_id)
    if rule is None:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    scheme, start = rule.scheme_code, rule.effective_from  # read before a rollback
    rule.effective_to = body.effective_to
    _save(
        db,
        lambda: _overlap_error(
            lambda: _subsidy_conflicts(db, scheme, start, body.effective_to, skip=rule_id),
            _describe_subsidy,
        ),
    )
    return _subsidy_out(rule)


# --- Settings ---


@router.get("/settings")
def list_settings(db: Session = Depends(get_db), _: User = Depends(readers)) -> list[dict]:
    rows = db.execute(select(Setting).order_by(Setting.key)).scalars()
    return [{"key": row.key, "value": row.value} for row in rows]


def _json_safe(value: Any) -> Any:
    """Store decimals as strings so JSON never turns 0.85 into a binary float (§3.7)."""
    if isinstance(value, float):
        return str(Decimal(str(value)))
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


@router.put("/settings/{key}")
def update_setting(
    key: str, body: SettingIn, db: Session = Depends(get_db), user: User = Depends(admin_only)
) -> dict:
    if key not in REQUIRED_KEYS:
        raise ApiError(404, "NOT_FOUND", "Unknown setting.")
    current = {row.key: row.value for row in db.execute(select(Setting)).scalars()}
    value = _json_safe(body.value)
    try:
        # Checked together with the other keys, so no key can break a cross-field rule.
        BusinessSettings.model_validate({**current, key: value})
    except ValidationError as exc:
        problems = [e["msg"] for e in exc.errors() if e["loc"] and e["loc"][0] == key]
        raise ApiError(
            422, "SETTING_INVALID", problems[0] if problems else "This value isn't allowed."
        ) from exc
    row = db.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=value)
        db.add(row)
    row.value = value
    row.updated_by = user.id
    row.updated_at = datetime.now(UTC)
    db.commit()
    return {"key": key, "value": value}
