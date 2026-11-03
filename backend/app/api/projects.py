"""Staff screen 8: projects, stage moves, status link; and recording the advance (§2, §12)."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_roles
from app.core.errors import ApiError
from app.models import Lead, Notification, Project, ProjectEvent, Quote, User
from app.models.enums import ProjectStage
from app.schemas.projects import (
    AdvanceIn,
    AdvanceOut,
    LinkState,
    NotificationOut,
    ProjectDetail,
    ProjectEventOut,
    ProjectRow,
    StageIn,
    TokenOut,
)
from app.services import projects

router = APIRouter(prefix="/staff", tags=["projects"])
staff_only = require_roles("sales", "admin")


def _row(db: Session, project: Project) -> dict:
    lead = db.get(Lead, project.lead_id)
    owner = db.get(User, lead.homeowner_id)
    quote = db.get(Quote, project.quote_id)
    days = (datetime.now(UTC) - project.stage_changed_at).days
    return {
        "id": project.id,
        "lead_id": lead.id,
        "code": lead.code,
        "homeowner_name": owner.full_name,
        "homeowner_locale": owner.preferred_locale.value,
        "stage": project.stage.value,
        "stage_changed_at": project.stage_changed_at,
        "days_in_stage": max(days, 0),
        "selected_kw": quote.selected_kw,
    }


def _detail(db: Session, project: Project) -> ProjectDetail:
    events = db.execute(
        select(ProjectEvent, User.full_name)
        .outerjoin(User, User.id == ProjectEvent.actor_id)
        .where(ProjectEvent.project_id == project.id)
        .order_by(ProjectEvent.created_at.desc())
    ).all()
    notes = db.execute(
        select(Notification)
        .where(Notification.lead_id == project.lead_id)
        .order_by(Notification.created_at.desc())
    ).scalars()
    return ProjectDetail(
        **_row(db, project),
        advance_amount=project.advance_amount,
        advance_reference=project.advance_reference,
        scheduled_for=projects.scheduled_date(db, project),
        stages=projects.stage_timeline(db, project),
        events=[
            ProjectEventOut(
                id=e.id,
                from_stage=e.from_stage.value if e.from_stage else None,
                to_stage=e.to_stage.value,
                actor_name=name,
                note=e.note,
                scheduled_for=e.scheduled_for,
                created_at=e.created_at,
            )
            for e, name in events
        ],
        notifications=[
            NotificationOut(
                id=n.id,
                type=n.type.value,
                channel=n.channel.value,
                locale=n.locale.value,
                recipient_masked=n.recipient_masked,
                message=n.message,
                delivery_status=n.delivery_status,
                created_at=n.created_at,
            )
            for n in notes
        ],
        link=LinkState(
            active=project.status_token_hash is not None
            and project.status_token_revoked_at is None,
            created_at=project.status_token_created_at,
            revoked_at=project.status_token_revoked_at,
        ),
    )


@router.post("/leads/{lead_id}/advance", response_model=AdvanceOut, status_code=201)
def record_advance(
    lead_id: uuid.UUID,
    body: AdvanceIn,
    db: Session = Depends(get_db),
    user: User = Depends(staff_only),
) -> AdvanceOut:
    project, token = projects.record_advance(db, lead_id, user, body.amount)
    db.commit()
    return AdvanceOut(project=_detail(db, project), status_token=token)


@router.get("/projects", response_model=list[ProjectRow])
def list_projects(db: Session = Depends(get_db), _: User = Depends(staff_only)) -> list[ProjectRow]:
    rows = db.execute(select(Project).order_by(Project.stage_changed_at)).scalars()
    return [ProjectRow(**_row(db, p)) for p in rows]


def _project_or_404(db: Session, project_id: uuid.UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    return project


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(staff_only)
) -> ProjectDetail:
    return _detail(db, _project_or_404(db, project_id))


@router.post("/projects/{project_id}/stage", response_model=ProjectDetail)
def move_stage(
    project_id: uuid.UUID,
    body: StageIn,
    db: Session = Depends(get_db),
    user: User = Depends(staff_only),
) -> ProjectDetail:
    project = projects.move_stage(
        db, project_id, user, ProjectStage(body.to), body.note, body.scheduled_for
    )
    db.commit()
    return _detail(db, project)


@router.post("/projects/{project_id}/link", response_model=TokenOut)
def regenerate_link(
    project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(staff_only)
) -> TokenOut:
    token = projects.regenerate_link(db, project_id, user)
    db.commit()
    return TokenOut(status_token=token)


@router.delete("/projects/{project_id}/link", status_code=204)
def revoke_link(
    project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(staff_only)
) -> Response:
    projects.revoke_link(db, project_id, user)
    db.commit()
    return Response(status_code=204)
