"""Idempotent seed: demo users, business rules, settings and the brief's sample leads."""

import hashlib
import io
from dataclasses import dataclass, field
from datetime import UTC, datetime

from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import BillFile, BillReading, Lead, PriceRule, Setting, SubsidyRule, User
from app.models.enums import (
    BillKind,
    Ownership,
    PropertyType,
    ReadingSource,
    ReadingStatus,
    RoofType,
    SubsidySegment,
    UserRole,
)
from app.services.qualification import qualify_lead
from seed import data

TABLES = ("users", "settings", "price_rules", "subsidy_rules", "leads", "bill_readings")


@dataclass
class SeedReport:
    created: dict[str, int] = field(default_factory=lambda: dict.fromkeys(TABLES, 0))
    skipped: dict[str, int] = field(default_factory=lambda: dict.fromkeys(TABLES, 0))

    def count(self, table: str, created: bool) -> None:
        bucket = self.created if created else self.skipped
        bucket[table] += 1


def _user(db: Session, report: SeedReport, role: str, password_hash: str, **fields) -> User:
    existing = db.execute(select(User).where(User.email == fields["email"])).scalar_one_or_none()
    if existing:
        report.count("users", created=False)
        return existing
    user = User(role=UserRole(role), password_hash=password_hash, **fields)
    db.add(user)
    db.flush()
    report.count("users", created=True)
    return user


def _placeholder_png() -> bytes:
    """An honest preview for a seeded reading: says there is no bill image."""
    image = Image.new("RGB", (900, 600), "#F2F6F5")
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(data.SEED_READING_PREVIEW_TEXT):
        draw.text((60, 240 + i * 40), line, fill="#18211F")
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _confirm_from_brief(db: Session, lead: Lead, units, bill, confirmed_by: User) -> None:
    """A typed-in (manual) confirmation of the brief's numbers, then the usual qualification."""
    png = _placeholder_png()
    file = BillFile(
        lead_id=lead.id,
        kind=BillKind.image,
        mime="image/png",
        size_bytes=len(png),
        sha256=hashlib.sha256(png + lead.code.encode()).hexdigest(),
        content=png,
        preview_png=png,
    )
    db.add(file)
    db.flush()
    reading = BillReading(
        lead_id=lead.id,
        bill_file_id=file.id,
        status=ReadingStatus.confirmed,
        source_path=ReadingSource.manual,
        avg_monthly_units=units,
        bill_amount=bill,
        edited_fields=["avg_monthly_units", "bill_amount"],
        confirmed_by=confirmed_by.id,
        confirmed_at=datetime.now(UTC),
    )
    db.add(reading)
    db.flush()
    lead.current_bill_reading_id = reading.id
    qualify_lead(db, lead, reading)


def run(db: Session, demo_password: str) -> SeedReport:
    report = SeedReport()
    password_hash = hash_password(demo_password)

    for staff in data.STAFF:
        _user(
            db,
            report,
            staff["role"],
            password_hash,
            full_name=staff["full_name"],
            email=staff["email"],
        )

    for key, value in data.SETTINGS.items():
        exists = db.get(Setting, key) is not None
        if not exists:
            db.add(Setting(key=key, value=value))
        report.count("settings", created=not exists)

    rule = data.PRICE_RULE
    exists = (
        db.execute(
            select(PriceRule.id).where(
                PriceRule.min_kw == rule["min_kw"],
                PriceRule.max_kw == rule["max_kw"],
                PriceRule.effective_from == rule["effective_from"],
            )
        ).first()
        is not None
    )
    if not exists:
        db.add(PriceRule(**rule))
    report.count("price_rules", created=not exists)

    rule = data.SUBSIDY_RULE
    exists = (
        db.execute(
            select(SubsidyRule.id).where(
                SubsidyRule.scheme_code == rule["scheme_code"],
                SubsidyRule.effective_from == rule["effective_from"],
            )
        ).first()
        is not None
    )
    if not exists:
        db.add(SubsidyRule(**{**rule, "segment": SubsidySegment(rule["segment"])}))
    report.count("subsidy_rules", created=not exists)

    db.flush()  # settings and rules must be visible to qualification below
    desk = db.execute(select(User).where(User.email == data.STAFF[0]["email"])).scalar_one()
    now = datetime.now(UTC)
    for item in data.HOMEOWNER_LEADS:
        owner = _user(db, report, "homeowner", password_hash, **item["user"])
        spec = item["lead"]
        exists = db.execute(select(Lead.id).where(Lead.code == spec["code"])).first() is not None
        if not exists:
            db.add(
                Lead(
                    code=spec["code"],
                    homeowner_id=owner.id,
                    ownership=Ownership(spec["ownership"]),
                    property_type=PropertyType.home,
                    roof_type=RoofType.rcc_flat,
                    roof_area_sqft=spec["roof_area_sqft"],
                    declared_monthly_bill=spec["declared_monthly_bill"],
                    pincode=spec["pincode"],
                    consent_at=now,
                    consent_version=data.CONSENT_VERSION,
                    seed_note=data.LEAD_SEED_NOTE,
                )
            )
        report.count("leads", created=not exists)

        lead = db.execute(select(Lead).where(Lead.code == spec["code"])).scalar_one()
        unread = lead.current_bill_reading_id is None
        if unread:
            _confirm_from_brief(
                db, lead, spec["avg_monthly_units"], spec["declared_monthly_bill"], desk
            )
        report.count("bill_readings", created=unread)

    db.commit()
    return report
