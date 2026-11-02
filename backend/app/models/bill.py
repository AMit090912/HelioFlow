import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, Integer, LargeBinary, Numeric, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.models.base import Base, IdMixin, pg_enum
from app.models.enums import BillKind, ReadingSource, ReadingStatus


class BillFile(IdMixin, Base):
    """Stored upload. Bytes are deferred so listing queries never load them (§3.3)."""

    __tablename__ = "bill_files"
    # Unique: the same file uploaded twice for one lead (e.g. a double-submit) is one reading.
    __table_args__ = (Index("uq_bill_files_lead_sha", "lead_id", "sha256", unique=True),)

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False
    )
    kind: Mapped[BillKind] = mapped_column(pg_enum(BillKind, "bill_kind"), nullable=False)
    mime: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[bytes] = deferred(mapped_column(LargeBinary, nullable=False))
    preview_png: Mapped[bytes | None] = deferred(mapped_column(LargeBinary))


class BillReading(IdMixin, Base):
    """Exactly one extraction per file. `ai_values` (AI) and the typed columns
    (human-confirmed) are kept apart for audit (§3.4)."""

    __tablename__ = "bill_readings"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True
    )
    bill_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bill_files.id"), nullable=False, unique=True
    )
    status: Mapped[ReadingStatus] = mapped_column(
        pg_enum(ReadingStatus, "reading_status"),
        nullable=False,
        default=ReadingStatus.processing,
        server_default="processing",
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quality: Mapped[dict | None] = mapped_column(JSONB)
    source_path: Mapped[ReadingSource | None] = mapped_column(
        pg_enum(ReadingSource, "reading_source")
    )
    attempts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    provider: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    ai_values: Mapped[dict | None] = mapped_column(JSONB)
    validation_flags: Mapped[dict | None] = mapped_column(JSONB)

    consumer_number: Mapped[str | None] = mapped_column(Text)
    tariff_category: Mapped[str | None] = mapped_column(Text)
    sanctioned_load_kw: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    monthly_units: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    avg_monthly_units: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    bill_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    fixed_charge_monthly: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    edited_fields: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
