import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, pg_enum
from app.models.enums import Locale, NotificationChannel, NotificationType


class Notification(IdMixin, Base):
    """Simulated WhatsApp/SMS outbox. Nothing is ever sent externally (§13)."""

    __tablename__ = "notifications"
    __table_args__ = (CheckConstraint("delivery_status = 'simulated'", name="simulated_only"),)

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id")
    )
    type: Mapped[NotificationType] = mapped_column(
        pg_enum(NotificationType, "notification_type"), nullable=False
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        pg_enum(NotificationChannel, "notification_channel"), nullable=False
    )
    locale: Mapped[Locale] = mapped_column(pg_enum(Locale, "locale"), nullable=False)
    recipient_masked: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="simulated", server_default="simulated"
    )
