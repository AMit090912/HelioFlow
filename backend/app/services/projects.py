"""Projects (§12): advance → six stages, append-only events, simulated notifications (§13) and
the public status link (only the token's SHA-256 is stored). Callers commit."""

import hashlib
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.models import Lead, Project, ProjectEvent, Quote, User
from app.models.enums import LeadStatus, ProjectStage, QuoteStatus
from app.services import notify
from app.services.lead_actions import lock_lead, log_event
from app.services.quotes import today_in_india

STAGES: tuple[ProjectStage, ...] = tuple(ProjectStage)  # declaration order is the lifecycle


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _issue_token(project: Project) -> str:
    token = secrets.token_urlsafe(32)
    project.status_token_hash = _hash(token)
    project.status_token_created_at = datetime.now(UTC)
    project.status_token_revoked_at = None
    return token


def _lock_project(db: Session, project_id: uuid.UUID) -> Project:
    project = db.get(Project, project_id, with_for_update=True, populate_existing=True)
    if project is None:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    return project


def _reason(note: str | None) -> str:
    cleaned = " ".join((note or "").split())
    if len(cleaned) < 5:
        raise ApiError(422, "REASON_REQUIRED", "Give a short reason (at least 5 characters).")
    return cleaned


def record_advance(
    db: Session, lead_id: uuid.UUID, actor: User, amount: Decimal
) -> tuple[Project, str]:
    lead = lock_lead(db, lead_id)
    if lead.status != LeadStatus.accepted:
        raise ApiError(
            409, "LEAD_STATUS_CONFLICT", "An advance can be recorded only after acceptance."
        )
    quote = db.execute(
        select(Quote).where(Quote.lead_id == lead.id, Quote.status == QuoteStatus.accepted)
    ).scalar_one_or_none()
    if quote is None:
        raise ApiError(409, "LEAD_STATUS_CONFLICT", "There is no accepted quote for this lead.")
    chosen = next(o for o in quote.snapshot["options"] if Decimal(o["kw"]) == quote.selected_kw)
    if amount > Decimal(chosen["net"]):
        raise ApiError(
            422, "ADVANCE_TOO_LARGE", "The advance can't be more than the cost after subsidy."
        )
    now = datetime.now(UTC)
    project = Project(
        lead_id=lead.id,
        quote_id=quote.id,
        stage=ProjectStage.advance_received,
        stage_changed_at=now,
        advance_amount=amount,
        # Payments are simulated (A-21): the reference says so in itself.
        advance_reference=f"SIMULATED-{secrets.token_hex(4).upper()}",
    )
    token = _issue_token(project)
    db.add(project)
    try:
        db.flush()
    except IntegrityError as exc:  # lead_id is unique: a project already exists
        raise ApiError(409, "LEAD_STATUS_CONFLICT", "This lead already has a project.") from exc
    db.add(
        ProjectEvent(
            project_id=project.id,
            from_stage=None,
            to_stage=ProjectStage.advance_received,
            actor_id=actor.id,
            note=f"Advance {notify.inr(amount)} ({project.advance_reference})",
        )
    )
    log_event(
        db, lead, actor, "converted", to_status=LeadStatus.converted, note=project.advance_reference
    )
    notify.project_created(db, lead, project.id, get_settings().frontend_origin)
    db.flush()
    return project, token


def move_stage(
    db: Session,
    project_id: uuid.UUID,
    actor: User,
    to: ProjectStage,
    note: str | None,
    scheduled_for: date | None,
) -> Project:
    """Forward exactly one step, or back exactly one step with a reason (§12)."""
    project = _lock_project(db, project_id)
    here = STAGES.index(project.stage)
    there = STAGES.index(to)
    if there == here + 1:
        cleaned = " ".join(note.split()) if note else None
    elif there == here - 1:
        cleaned = _reason(note)
    else:
        raise ApiError(409, "STAGE_NOT_NEXT", "Move one stage at a time.")
    if scheduled_for is None and there < here and to == ProjectStage.installation_scheduled:
        # A correction back to "scheduled" keeps the agreed date unless a new one is given.
        scheduled_for = scheduled_date(db, project)
    elif scheduled_for is not None:
        if to != ProjectStage.installation_scheduled:
            raise ApiError(422, "VALIDATION_ERROR", "A date only goes with scheduling.")
        if scheduled_for < today_in_india():
            raise ApiError(422, "DATE_IN_PAST", "The installation date can't be in the past.")
        if scheduled_for > today_in_india() + timedelta(days=730):
            raise ApiError(422, "DATE_TOO_FAR", "Pick an installation date within two years.")
    db.add(
        ProjectEvent(
            project_id=project.id,
            from_stage=project.stage,
            to_stage=to,
            actor_id=actor.id,
            note=cleaned or None,
            scheduled_for=scheduled_for,
        )
    )
    project.stage = to
    project.stage_changed_at = datetime.now(UTC)
    notify.stage_changed(db, db.get(Lead, project.lead_id), project.id, to.value, scheduled_for)
    db.flush()
    return project


def regenerate_link(db: Session, project_id: uuid.UUID, actor: User) -> str:
    """The old token stops working the moment its hash is replaced."""
    project = _lock_project(db, project_id)
    token = _issue_token(project)
    log_event(db, db.get(Lead, project.lead_id), actor, "link_regenerated")
    return token


def revoke_link(db: Session, project_id: uuid.UUID, actor: User) -> None:
    project = _lock_project(db, project_id)
    if project.status_token_revoked_at is not None:
        return  # already off: keep the first revocation time and log it once
    project.status_token_revoked_at = datetime.now(UTC)
    log_event(db, db.get(Lead, project.lead_id), actor, "link_revoked")


def scheduled_date(db: Session, project: Project) -> date | None:
    """The date from the latest move into "installation scheduled", while still relevant."""
    if STAGES.index(project.stage) < STAGES.index(ProjectStage.installation_scheduled):
        return None
    return db.execute(
        select(ProjectEvent.scheduled_for)
        .where(
            ProjectEvent.project_id == project.id,
            ProjectEvent.to_stage == ProjectStage.installation_scheduled,
        )
        .order_by(ProjectEvent.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def stage_timeline(db: Session, project: Project) -> list[dict[str, Any]]:
    """Each stage with when it was first reached. A correction back clears the stages after it
    (they are reached again later) but keeps the date of the stage it returns to."""
    reached: dict[ProjectStage, datetime] = {}
    events = db.execute(
        select(ProjectEvent)
        .where(ProjectEvent.project_id == project.id)
        .order_by(ProjectEvent.created_at)
    ).scalars()
    for event in events:
        to = STAGES.index(event.to_stage)
        if event.from_stage is not None and STAGES.index(event.from_stage) > to:
            for later in STAGES[to + 1 :]:
                reached.pop(later, None)
        reached.setdefault(event.to_stage, event.created_at)
    current = STAGES.index(project.stage)
    return [
        {
            "stage": stage.value,
            "done_at": reached[stage].isoformat() if i <= current and stage in reached else None,
        }
        for i, stage in enumerate(STAGES)
    ]


def public_status(db: Session, token: str) -> dict[str, Any]:
    """Only what §12 allows: first name, code, stages and the planned date."""
    inactive = ApiError(404, "LINK_INACTIVE", "This link is no longer active.")
    if not token or len(token) > 100:
        raise inactive
    project = db.execute(
        select(Project).where(Project.status_token_hash == _hash(token))
    ).scalar_one_or_none()
    if project is None or project.status_token_revoked_at is not None:
        raise inactive
    lead = db.get(Lead, project.lead_id)
    owner = db.get(User, lead.homeowner_id)
    scheduled = scheduled_date(db, project)
    return {
        "first_name": owner.full_name.split()[0] if owner.full_name.strip() else "",
        "code": lead.code,
        "current_stage": project.stage.value,
        "stages": stage_timeline(db, project),
        "scheduled_for": scheduled.isoformat() if scheduled else None,
    }
