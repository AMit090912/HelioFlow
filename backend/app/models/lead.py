import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CHAR, CheckConstraint, DateTime, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, pg_enum
from app.models.enums import (
    LeadScore,
    LeadStatus,
    NextAction,
    Ownership,
    PropertyType,
    RoofType,
    RoofVerifiedVia,
)


class Lead(IdMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        CheckConstraint("roof_area_sqft > 0", name="roof_area_positive"),
        CheckConstraint("declared_monthly_bill > 0", name="bill_positive"),
        CheckConstraint("pincode ~ '^[1-9][0-9]{5}$'", name="pincode_format"),
        CheckConstraint(
            "verified_roof_area_sqft IS NULL OR verified_roof_area_sqft > 0",
            name="verified_roof_positive",
        ),
        CheckConstraint(
            "verified_sanctioned_load_kw IS NULL OR "
            "(verified_sanctioned_load_kw > 0 AND verified_sanctioned_load_kw <= 100)",
            name="verified_load_range",
        ),
        Index("ix_leads_inbox", "status", "score", text("created_at DESC")),
    )

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    homeowner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    ownership: Mapped[Ownership] = mapped_column(pg_enum(Ownership, "ownership"), nullable=False)
    property_type: Mapped[PropertyType] = mapped_column(
        pg_enum(PropertyType, "property_type"), nullable=False
    )
    roof_type: Mapped[RoofType] = mapped_column(pg_enum(RoofType, "roof_type"), nullable=False)
    roof_area_sqft: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    declared_monthly_bill: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    pincode: Mapped[str] = mapped_column(CHAR(6), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consent_version: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[LeadStatus] = mapped_column(
        pg_enum(LeadStatus, "lead_status"),
        nullable=False,
        default=LeadStatus.draft,
        server_default="draft",
    )
    score: Mapped[LeadScore | None] = mapped_column(pg_enum(LeadScore, "lead_score"))
    score_reasons: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    recommended_kw: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    sizing_detail: Mapped[dict | None] = mapped_column(JSONB)
    next_action: Mapped[NextAction | None] = mapped_column(pg_enum(NextAction, "next_action"))

    verified_roof_area_sqft: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    roof_verified_via: Mapped[RoofVerifiedVia | None] = mapped_column(
        pg_enum(RoofVerifiedVia, "roof_verified_via")
    )
    roof_verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    roof_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Staff-entered sanctioned load from the DISCOM record; wins over the bill's value (§8).
    verified_sanctioned_load_kw: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    load_verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", name="fk_leads_load_verified_by_users")
    )
    load_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    survey_notes: Mapped[str | None] = mapped_column(Text)
    surveyed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    surveyed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    # FK added with use_alter: bill_readings also references leads (cycle).
    current_bill_reading_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bill_readings.id", use_alter=True, name="fk_leads_current_bill_reading"),
    )
    # Labels synthetic seed values that are not part of the client brief (§8.1).
    seed_note: Mapped[str | None] = mapped_column(Text)
