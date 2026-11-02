"""Effective-dated business rules (§3.5–§3.7).

The no-overlap EXCLUDE constraints live in the Alembic migration
(`0001_baseline`) as raw SQL, because they use range expressions that
autogenerate cannot represent faithfully.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, pg_enum
from app.models.enums import SubsidySegment


class PriceRule(IdMixin, Base):
    __tablename__ = "price_rules"
    __table_args__ = (
        CheckConstraint("min_kw > 0 AND min_kw <= max_kw", name="kw_range"),
        CheckConstraint("price_per_kw > 0", name="price_positive"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="date_order"
        ),
    )

    min_kw: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_kw: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    price_per_kw: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gst_inclusive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class SubsidyRule(IdMixin, Base):
    __tablename__ = "subsidy_rules"
    __table_args__ = (
        CheckConstraint("cap_amount >= 0", name="cap_non_negative"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="date_order"
        ),
    )

    scheme_code: Mapped[str] = mapped_column(Text, nullable=False)
    segment: Mapped[SubsidySegment] = mapped_column(
        pg_enum(SubsidySegment, "subsidy_segment"), nullable=False
    )
    slabs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    cap_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source_note: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class Setting(Base):
    """Key/value business settings; each key is validated by a Pydantic model."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
