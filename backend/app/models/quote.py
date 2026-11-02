"""Quotes: immutable commercial content, controlled lifecycle (§3.8, §11).

The `quotes_guard` trigger in the baseline migration enforces immutability and
the allowed transitions (sent→accepted, sent→superseded) in the database itself.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, pg_enum
from app.models.enums import QuoteStatus


class Quote(IdMixin, Base):
    __tablename__ = "quotes"
    __table_args__ = (
        Index(
            "uq_quotes_one_open_per_lead",
            "lead_id",
            unique=True,
            postgresql_where=text("status = 'sent'"),
        ),
        # Lifecycle fields must agree with status, so a superseded quote can never carry
        # acceptance data (and vice versa) — the trigger alone only stops re-setting a field.
        CheckConstraint(
            "(status = 'accepted') = "
            "(accepted_at IS NOT NULL AND accepted_by IS NOT NULL AND selected_kw IS NOT NULL)",
            name="accepted_fields_match_status",
        ),
        CheckConstraint(
            "(status = 'superseded') = (superseded_at IS NOT NULL)",
            name="superseded_fields_match_status",
        ),
    )

    # Immutable after insert
    number: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True
    )
    priced_on: Mapped[date] = mapped_column(Date, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    calc_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Lifecycle — each set once, only via allowed transitions
    status: Mapped[QuoteStatus] = mapped_column(
        pg_enum(QuoteStatus, "quote_status"),
        nullable=False,
        default=QuoteStatus.sent,
        server_default="sent",
    )
    selected_kw: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_by_quote_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quotes.id")
    )
