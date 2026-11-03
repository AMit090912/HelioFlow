"""Bill upload, reading status, private preview and confirmation (ARCHITECTURE §5, §6)."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_owned_or_404, require_roles
from app.core.errors import ApiError
from app.core.ratelimit import SlidingWindowLimiter
from app.models import BillFile, BillReading, Lead, User
from app.models.enums import ReadingStatus, UserRole
from app.schemas.bills import ConfirmIn, ReadingOut
from app.services.bill_reading import (
    UPLOADABLE,
    accept_upload,
    confirm_reading,
    process_reading,
    sweep_if_stale,
)
from app.services.calc.errors import CalcError
from app.services.uploads import UploadError

router = APIRouter(tags=["bills"])
_CHUNK = 1024 * 1024


async def _read_capped(file: UploadFile, max_mb: int) -> bytes:
    """Read at most max_mb + 1 byte into memory. (The multipart parser has already spooled the
    part to a temp file; the request-size middleware in main.py rejects oversized bodies first.)"""
    limit = max_mb * 1024 * 1024 + 1
    data = bytearray()
    while chunk := await file.read(_CHUNK):
        data.extend(chunk)
        if len(data) >= limit:
            break
    return bytes(data)


def _owned_reading(db: Session, reading_id: uuid.UUID, user: User) -> BillReading:
    reading = db.get(BillReading, reading_id)
    if reading is None:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    if user.role == UserRole.homeowner:
        lead = db.get(Lead, reading.lead_id)
        if lead is None or lead.homeowner_id != user.id:
            raise ApiError(404, "NOT_FOUND", "Not found.")  # 404, never 403 (§4)
    return reading


def _out(db: Session, reading: BillReading) -> ReadingOut:
    return ReadingOut.of(reading, kind=db.get(BillFile, reading.bill_file_id).kind.value)


@router.post("/leads/{lead_id}/bills", response_model=ReadingOut, status_code=202)
async def upload_bill(
    lead_id: uuid.UUID,
    file: UploadFile,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("homeowner")),  # §4: uploading is the homeowner's action
):
    lead = get_owned_or_404(db, Lead, lead_id, user)
    limiter: SlidingWindowLimiter = request.app.state.upload_limiter
    key = f"upload|{user.id}"
    if limiter.is_blocked(key):
        raise ApiError(429, "RATE_LIMITED", "Too many uploads. Try again later.")
    limiter.record(key)

    max_mb = get_settings().max_upload_mb
    data = await _read_capped(file, max_mb)
    try:
        # PDF parsing, rendering and image work are CPU-bound: keep them off the event loop.
        accepted = await run_in_threadpool(accept_upload, db, lead, data, max_mb)
    except UploadError as exc:
        raise ApiError(exc.status, exc.code, exc.message) from exc

    if accepted.needs_ai:
        background.add_task(
            process_reading,
            accepted.reading.id,
            request.app.state.session_factory,
            request.app.state.ai_providers,
        )
    body = _out(db, accepted.reading).model_dump(mode="json")
    return JSONResponse(body, status_code=202 if accepted.created else 200)


@router.get("/bills/{reading_id}", response_model=ReadingOut)
def get_reading(
    reading_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> ReadingOut:
    reading = _owned_reading(db, reading_id, user)
    sweep_if_stale(db, reading)
    return _out(db, reading)


@router.get("/bills/{reading_id}/preview")
def preview(
    reading_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Response:
    reading = _owned_reading(db, reading_id, user)
    file = db.get(BillFile, reading.bill_file_id)
    return Response(
        content=file.preview_png,
        media_type="image/png",
        headers={"Cache-Control": "private, no-store", "Content-Disposition": "inline"},
    )


@router.post("/bills/{reading_id}/confirm", response_model=ReadingOut)
def confirm(
    reading_id: uuid.UUID,
    values: ConfirmIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("homeowner")),  # staff re-edit is a separate flow (§6.4)
) -> ReadingOut:
    reading = _owned_reading(db, reading_id, user)
    sweep_if_stale(db, reading)
    # Lock the lead so two confirms (double tap, two tabs) run one after the other, then re-read
    # the reading under that lock before deciding anything.
    lead = db.get(Lead, reading.lead_id, with_for_update=True, populate_existing=True)
    db.refresh(reading)
    if reading.status == ReadingStatus.processing:
        raise ApiError(409, "READING_IN_PROGRESS", "The bill is still being read.")
    if reading.status == ReadingStatus.confirmed:
        raise ApiError(409, "READING_ALREADY_CONFIRMED", "These values are already confirmed.")
    if lead.status not in UPLOADABLE:
        # Another reading already qualified this lead; status only moves forward (§2).
        raise ApiError(409, "LEAD_LOCKED", "This lead has moved past the bill step.")
    try:
        confirmed = confirm_reading(db, reading, values, user)
    except ValidationError as exc:  # an AI value kept unchanged broke the rules
        details = [
            {"field": ".".join(str(p) for p in e["loc"]), "type": e["type"]} for e in exc.errors()
        ]
        raise ApiError(422, "VALIDATION_ERROR", "Some values need checking.", details) from exc
    except CalcError as exc:  # business settings missing/invalid: an operator problem, not theirs
        db.rollback()
        raise ApiError(500, exc.code, "Scoring is not configured correctly.") from exc
    return _out(db, confirmed)
