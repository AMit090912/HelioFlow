import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, pg_enum
from app.models.enums import LeadStatus

EVENT_KINDS = (
    "verified",
    "upgraded",
    "closed",
    "quote_sent",
    "quote_accepted",
    "converted",
    "link_regenerated",
    "link_revoked",
)


class LeadEvent(IdMixin, Base):
    """Append-only audit of actions on a lead: who, when, status from → to, and why."""

    __tablename__ = "lead_events"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('verified','upgraded','closed','quote_sent','quote_accepted',"
            "'converted','link_regenerated','link_revoked')",
            # Migrations named it "ck_lead_events_kind", which the naming convention prefixed again.
            name="ck_lead_events_kind",
        ),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    from_status: Mapped[LeadStatus | None] = mapped_column(pg_enum(LeadStatus, "lead_status"))
    to_status: Mapped[LeadStatus | None] = mapped_column(pg_enum(LeadStatus, "lead_status"))
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)
