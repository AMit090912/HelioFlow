import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_serializer

from app.schemas.bills import plain

StageName = Literal[
    "advance_received",
    "installation_scheduled",
    "installation_completed",
    "net_metering_completed",
    "subsidy_applied",
    "subsidy_credited",
]


class AdvanceIn(BaseModel):
    amount: Decimal = Field(gt=0, le=10_000_000)


class StageIn(BaseModel):
    to: StageName
    note: str | None = Field(default=None, max_length=1000)
    scheduled_for: date | None = None


class ProjectRow(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    code: str
    homeowner_name: str
    homeowner_locale: str  # the status link and messages use the homeowner's language
    stage: str
    stage_changed_at: datetime
    days_in_stage: int
    selected_kw: Decimal | None

    @field_serializer("selected_kw")
    def _kw(self, value: Decimal | None) -> str | None:
        return plain(value)


class ProjectEventOut(BaseModel):
    id: uuid.UUID
    from_stage: str | None
    to_stage: str
    actor_name: str | None
    note: str | None
    scheduled_for: date | None
    created_at: datetime


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    channel: str
    locale: str
    recipient_masked: str
    message: str
    delivery_status: str
    created_at: datetime


class LinkState(BaseModel):
    active: bool
    created_at: datetime | None
    revoked_at: datetime | None


class ProjectDetail(ProjectRow):
    advance_amount: Decimal
    advance_reference: str
    scheduled_for: date | None
    stages: list[dict[str, Any]]
    events: list[ProjectEventOut]
    notifications: list[NotificationOut]
    link: LinkState

    @field_serializer("advance_amount")
    def _amount(self, value: Decimal) -> str | None:
        return plain(value)


class AdvanceOut(BaseModel):
    project: ProjectDetail
    status_token: str  # shown once; only its hash is stored


class TokenOut(BaseModel):
    status_token: str
