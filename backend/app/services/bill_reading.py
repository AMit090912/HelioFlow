"""Bill reading workflow (ARCHITECTURE §5, §6): accept → (background) read → confirm.

The upload request only validates, stores and runs the cheap deterministic photo check; the AI
chain runs afterwards so the request never waits on Groq/Gemini (§1). A lead is never lost: if
every provider fails, the reading moves to `failed_manual` and the person types the values in.
"""

import hashlib
import logging
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import BillFile, BillReading, Lead, User
from app.models.enums import BillKind, LeadStatus, ReadingSource, ReadingStatus
from app.schemas.bills import ConfirmIn
from app.services.ai import Provider, run_chain, sanity_flags
from app.services.ai.validation import monthly_figures
from app.services.qualification import qualify_lead
from app.services.uploads import (
    UploadError,
    check_quality,
    check_size,
    inspect_pdf,
    normalise_image,
    pages_to_render,
    relevant_text_pages,
    render_pages,
    sniff,
)

log = logging.getLogger("helio.bills")
STALE_AFTER = timedelta(minutes=2)
SessionFactory = Callable[[], AbstractContextManager[Session]]
ProvidersFor = Callable[[str], list[Provider]]  # upload sha256 → provider chain


@dataclass(frozen=True)
class Accepted:
    reading: BillReading
    created: bool  # False when the same file was already uploaded for this lead
    needs_ai: bool


# A bill can be (re)uploaded only until the lead is qualified; after that the confirmed values
# drive scoring and quotes, and changes go through the staff re-edit flow (§6.4).
UPLOADABLE = {LeadStatus.draft, LeadStatus.bill_processing, LeadStatus.bill_review}


def _find_reading(db: Session, lead_id: uuid.UUID, sha: str) -> BillReading | None:
    return (
        db.execute(
            select(BillReading)
            .join(BillFile, BillFile.id == BillReading.bill_file_id)
            .where(BillFile.lead_id == lead_id, BillFile.sha256 == sha)
        )
        .scalars()
        .first()
    )


def _existing_reading(db: Session, lead_id: uuid.UUID, sha: str) -> BillReading | None:
    """Dedupe per lead only — never across leads or users (§5.1)."""
    return _find_reading(db, lead_id, sha)


def accept_upload(db: Session, lead: Lead, data: bytes, max_mb: int) -> Accepted:
    if lead.status not in UPLOADABLE:
        raise UploadError("LEAD_LOCKED", "This lead has moved past the bill step.", status=409)
    check_size(data, max_mb)
    kind = sniff(data)
    sha = hashlib.sha256(data).hexdigest()

    existing = _existing_reading(db, lead.id, sha)
    if existing is not None:
        if existing.status == ReadingStatus.failed_manual and existing.confirmed_at is None:
            # Same file after an AI outage: the person expects us to try again.
            existing.status = ReadingStatus.processing
            existing.processing_started_at = datetime.now(UTC)
            existing.attempts = [*existing.attempts, {"outcome": "retry_requested"}]
            lead.status = LeadStatus.bill_processing
            db.commit()
            return Accepted(existing, created=True, needs_ai=True)
        return Accepted(existing, created=False, needs_ai=False)

    if kind == "pdf":
        info = inspect_pdf(data)
        text_pages = relevant_text_pages(info)
        stored, page_count = data, info.page_count
        if text_pages:
            source, quality = ReadingSource.pdf_text, None
            preview = render_pages(data, [0])[0].preview_png
        else:
            source = ReadingSource.vision
            rendered = render_pages(data, pages_to_render(info))  # rendered once, size-capped
            preview, quality = rendered[0].preview_png, check_quality(rendered[0].jpeg)
    else:
        image = normalise_image(data)
        stored, preview, page_count = image.jpeg, image.preview_png, None
        source, quality = ReadingSource.vision, check_quality(image.jpeg)

    bill_file = BillFile(
        lead_id=lead.id,
        kind=BillKind.pdf if kind == "pdf" else BillKind.image,
        mime="application/pdf" if kind == "pdf" else "image/jpeg",
        size_bytes=len(stored),
        sha256=sha,
        page_count=page_count,
        content=stored,
        preview_png=preview,
    )
    try:
        db.add(bill_file)
        db.flush()
    except IntegrityError:
        # Lost a race with a concurrent upload of the same file (double-submit): use its reading.
        db.rollback()
        winner = _find_reading(db, lead.id, sha)
        if winner is None:
            raise
        return Accepted(winner, created=False, needs_ai=False)

    photo_ok = quality is None or quality.ok
    reading = BillReading(
        lead_id=lead.id,
        bill_file_id=bill_file.id,
        status=ReadingStatus.processing if photo_ok else ReadingStatus.needs_reupload,
        processing_started_at=datetime.now(UTC) if photo_ok else None,
        source_path=source,
        quality=None
        if quality is None
        else {
            "ok": quality.ok,
            "reasons": list(quality.reasons),
            "metrics": quality.metrics,
        },
    )
    db.add(reading)
    if photo_ok:
        lead.status = LeadStatus.bill_processing
    db.commit()
    return Accepted(reading, created=True, needs_ai=photo_ok)


@dataclass(frozen=True)
class _Job:
    kind: BillKind
    source: ReadingSource | None
    content: bytes
    sha256: str
    declared_bill: Decimal


def _payload(job: _Job) -> tuple[list[bytes] | None, str | None]:
    if job.kind == BillKind.image:
        return [job.content], None
    info = inspect_pdf(job.content)
    if job.source == ReadingSource.pdf_text:
        return None, "\n\n".join(info.pages_text[i] for i in relevant_text_pages(info))
    return [page.jpeg for page in render_pages(job.content, pages_to_render(info))], None


def _locked_if_processing(db: Session, reading_id: uuid.UUID) -> BillReading | None:
    """Re-read under a row lock: write only if nobody swept or confirmed it meanwhile."""
    reading = db.get(BillReading, reading_id, with_for_update=True, populate_existing=True)
    if reading is None or reading.status != ReadingStatus.processing:
        return None
    return reading


def process_reading(
    reading_id: uuid.UUID, session_factory: SessionFactory, providers_for: ProvidersFor
) -> None:
    """Background job. Loads its inputs, releases the DB connection while the AI works (up to the
    chain budget), then writes only if the reading is still processing. Never raises."""
    with session_factory() as db:
        reading = db.get(BillReading, reading_id)
        if reading is None or reading.status != ReadingStatus.processing:
            return
        file = db.get(BillFile, reading.bill_file_id)
        lead = db.get(Lead, reading.lead_id)
        job = _Job(
            file.kind, reading.source_path, file.content, file.sha256, lead.declared_monthly_bill
        )

    try:
        images, text = _payload(job)
        result = run_chain(providers_for(job.sha256), images=images, text=text)
    except Exception as exc:  # keep the lead: fall back to manual entry
        log.error("bill reading crashed (%s) for reading %s", type(exc).__name__, reading_id)
        result = None

    with session_factory() as db:
        reading = _locked_if_processing(db, reading_id)
        if reading is None:
            log.info(
                "bill reading %s changed while the AI was reading; result discarded", reading_id
            )
            return
        if result is None:
            reading.attempts = [*reading.attempts, {"outcome": "error", "error_code": "internal"}]
            reading.status = ReadingStatus.failed_manual
        elif result.extraction is None:
            reading.attempts = [*reading.attempts, *result.attempts]
            reading.status = ReadingStatus.failed_manual
        else:
            attempts = list(result.attempts)
            attempts[-1] = {**attempts[-1], "raw": result.raw}  # kept server-side, never logged
            extraction = result.extraction
            flags = sanity_flags(extraction, declared_bill=job.declared_bill)
            monthly = monthly_figures(extraction)
            # What the person is asked to confirm: per-month figures, never a 3-month total.
            flags["_suggested"] = {  # type: ignore[assignment]
                "avg_monthly_units": _str(monthly.avg_monthly_units),
                "method": monthly.method,
                "bill_amount": _str(monthly.bill_amount),
                "fixed_charge_monthly": _str(monthly.fixed_charge),
                "billing_days": monthly.billing_days,
            }
            reading.attempts = [*reading.attempts, *attempts]
            reading.ai_values = extraction.model_dump(mode="json")
            reading.validation_flags = flags
            reading.provider, reading.model = result.provider, result.model
            reading.prompt_version = attempts[-1]["prompt_version"]
            # The values decide, not the model's opinion of the photo: if the units it needs
            # were read, the person checks them; re-upload only when nothing usable came back.
            unreadable = monthly.avg_monthly_units is None and bool(
                {"not_electricity_bill", "legibility_poor"} & set(flags.get("document", []))
            )
            reading.status = (
                ReadingStatus.needs_reupload if unreadable else ReadingStatus.needs_review
            )
        _back_to_review(db, reading.lead_id)
        db.commit()


def _back_to_review(db: Session, lead_id: Any) -> None:
    """A finished (or abandoned) read puts the lead in bill review, but never pulls back a lead
    that another reading has already moved past the bill step: status only moves forward."""
    lead = db.get(Lead, lead_id)
    if lead is not None and lead.status in UPLOADABLE:
        lead.status = LeadStatus.bill_review


def sweep_if_stale(db: Session, reading: BillReading, now: datetime | None = None) -> None:
    """A reading orphaned mid-read (e.g. server restart) becomes manual entry after 2 minutes."""
    now = now or datetime.now(UTC)
    started = reading.processing_started_at or reading.created_at
    if reading.status == ReadingStatus.processing and now - started > STALE_AFTER:
        reading.attempts = [*reading.attempts, {"outcome": "error", "error_code": "stale"}]
        reading.status = ReadingStatus.failed_manual
        _back_to_review(db, reading.lead_id)
        db.commit()


def _str(value: Any) -> str | None:
    return None if value is None else str(value)


def _norm(value: Any) -> str | None:
    """Comparable form, so "340.00", 340 and Decimal("340") count as the same value."""
    if value is None:
        return None
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    try:
        return format(Decimal(str(value)).normalize(), "f")
    except (InvalidOperation, ValueError):
        return " ".join(str(value).split()).lower()


def confirm_reading(
    db: Session, reading: BillReading, values: ConfirmIn, actor: User
) -> BillReading:
    ai = reading.ai_values or {}
    suggested = (reading.validation_flags or {}).get("_suggested", {})
    ai_units = (ai.get("monthly_units") or {}).get("value")
    proposals = {
        "consumer_number": (ai.get("consumer_number") or {}).get("value"),
        "tariff_category": (ai.get("tariff_category") or {}).get("value"),
        "sanctioned_load_kw": (ai.get("sanctioned_load_kw") or {}).get("value"),
        "monthly_units": [m["units"] for m in ai_units] if ai_units else None,
        "avg_monthly_units": suggested.get("avg_monthly_units"),
        # Per-month figures when the bill covers another period (A-30); bill-v1 readings have no
        # such suggestion and fall back to the value as read.
        "bill_amount": suggested.get("bill_amount", (ai.get("bill_amount") or {}).get("value")),
        "fixed_charge_monthly": suggested.get(
            "fixed_charge_monthly", (ai.get("fixed_charge") or {}).get("value")
        ),
    }
    # A field the person didn't send keeps the AI's proposal; sending null clears it. The merged
    # result is validated again, so an AI value (e.g. 3000 "kW" that was really watts) gets the
    # same checks as a typed one. Raises pydantic.ValidationError → 422.
    sent = values.model_dump()
    merged = {k: sent[k] if k in values.model_fields_set else proposals[k] for k in sent}
    confirmed = ConfirmIn.model_validate(merged).model_dump()
    if reading.ai_values is None:
        edited = sorted(k for k, v in confirmed.items() if v is not None)  # all typed by hand
        reading.source_path = ReadingSource.manual
    else:
        edited = sorted(k for k, v in confirmed.items() if _norm(v) != _norm(proposals[k]))

    reading.consumer_number = confirmed["consumer_number"]
    reading.tariff_category = confirmed["tariff_category"]
    reading.sanctioned_load_kw = confirmed["sanctioned_load_kw"]
    reading.monthly_units = confirmed["monthly_units"]
    reading.avg_monthly_units = confirmed["avg_monthly_units"]
    reading.bill_amount = confirmed["bill_amount"]
    reading.fixed_charge_monthly = confirmed["fixed_charge_monthly"]
    reading.edited_fields = edited
    reading.confirmed_by = actor.id
    reading.confirmed_at = datetime.now(UTC)
    reading.status = ReadingStatus.confirmed
    lead = db.get(Lead, reading.lead_id)
    lead.current_bill_reading_id = reading.id
    db.flush()
    qualify_lead(db, lead, reading)  # score + provisional size, same transaction (§7, §8)
    db.commit()
    return reading
