import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, pg_enum
from app.models.enums import ProjectStage

STAGE_ENUM = pg_enum(ProjectStage, "project_stage")


class Project(IdMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_stage", "stage", "stage_changed_at"),)

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, unique=True
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quotes.id"), nullable=False
    )
    stage: Mapped[ProjectStage] = mapped_column(
        STAGE_ENUM,
        nullable=False,
        default=ProjectStage.advance_received,
        server_default="advance_received",
    )
    stage_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    advance_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    advance_reference: Mapped[str] = mapped_column(Text, nullable=False)
    # Only the SHA-256 of the public status token is stored (§12).
    status_token_hash: Mapped[str | None] = mapped_column(CHAR(64), unique=True)
    status_token_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_token_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectEvent(IdMixin, Base):
    """Append-only stage history; doubles as the audit log."""

    __tablename__ = "project_events"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    from_stage: Mapped[ProjectStage | None] = mapped_column(STAGE_ENUM)
    to_stage: Mapped[ProjectStage] = mapped_column(STAGE_ENUM, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)
