"""Database-level guarantees from ARCHITECTURE §3 (Rev 3)."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    BillFile,
    BillReading,
    Lead,
    PriceRule,
    Quote,
    SubsidyRule,
    User,
)
from app.models.enums import (
    BillKind,
    Ownership,
    PropertyType,
    QuoteStatus,
    RoofType,
    SubsidySegment,
    UserRole,
)

NOW = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)


def make_user(db: Session, email: str = "owner@example.com", **kw) -> User:
    user = User(
        role=kw.pop("role", UserRole.homeowner),
        full_name="Test Owner",
        email=email,
        password_hash="x",
        **kw,
    )
    db.add(user)
    db.flush()
    return user


def make_lead(db: Session, owner: User, code: str = "LD-1") -> Lead:
    lead = Lead(
        code=code,
        homeowner_id=owner.id,
        ownership=Ownership.owner,
        property_type=PropertyType.home,
        roof_type=RoofType.rcc_flat,
        roof_area_sqft=Decimal("400"),
        declared_monthly_bill=Decimal("3200"),
        pincode="440010",
        consent_at=NOW,
        consent_version="v1",
    )
    db.add(lead)
    db.flush()
    return lead


def make_quote(db: Session, lead: Lead, owner: User, number: str = "HF-Q-1") -> Quote:
    quote = Quote(
        number=number,
        lead_id=lead.id,
        status=QuoteStatus.sent,
        priced_on=date(2026, 11, 2),
        snapshot={"options": [{"kw": "3"}]},
        calc_version="calc-1.0.0",
        created_by=owner.id,
        sent_at=NOW,
    )
    db.add(quote)
    db.flush()
    return quote


def test_extensions_present(db_session: Session):
    names = set(db_session.execute(text("SELECT extname FROM pg_extension")).scalars())
    assert {"citext", "btree_gist"} <= names


def test_email_unique_case_insensitive(db_session: Session):
    make_user(db_session, "A@x.com")
    with pytest.raises(IntegrityError):
        make_user(db_session, "a@x.com")
    db_session.rollback()


def test_user_needs_email_or_phone(db_session: Session):
    with pytest.raises(IntegrityError):
        make_user(db_session, email=None)
    db_session.rollback()


def test_bill_reading_unique_per_file(db_session: Session):
    owner = make_user(db_session)
    lead = make_lead(db_session, owner)
    f = BillFile(
        lead_id=lead.id,
        kind=BillKind.image,
        mime="image/jpeg",
        size_bytes=10,
        sha256="a" * 64,
        content=b"x",
    )
    db_session.add(f)
    db_session.flush()
    db_session.add(BillReading(lead_id=lead.id, bill_file_id=f.id))
    db_session.flush()
    with pytest.raises(IntegrityError):
        db_session.add(BillReading(lead_id=lead.id, bill_file_id=f.id))
        db_session.flush()
    db_session.rollback()


def _price(min_kw: str, max_kw: str, start: date, end: date | None) -> PriceRule:
    return PriceRule(
        min_kw=Decimal(min_kw),
        max_kw=Decimal(max_kw),
        price_per_kw=Decimal("60000"),
        gst_inclusive=True,
        effective_from=start,
        effective_to=end,
    )


def test_price_rule_overlap_rejected(db_session: Session):
    db_session.add(_price("1", "10", date(2026, 1, 1), None))
    db_session.flush()
    # Adjacent earlier period does not overlap.
    db_session.add(_price("1", "10", date(2025, 1, 1), date(2025, 12, 31)))
    db_session.flush()
    with pytest.raises(IntegrityError):
        db_session.add(_price("3", "5", date(2026, 6, 1), None))
        db_session.flush()
    db_session.rollback()


def _subsidy(scheme: str, start: date, end: date | None) -> SubsidyRule:
    return SubsidyRule(
        scheme_code=scheme,
        segment=SubsidySegment.residential,
        slabs=[{"from_kw": "0", "to_kw": "2", "amount_per_kw": "30000"}],
        cap_amount=Decimal("78000"),
        effective_from=start,
        effective_to=end,
        source_note="test",
    )


def test_subsidy_rule_overlap_rejected(db_session: Session):
    db_session.add(_subsidy("CENTRAL_RESIDENTIAL", date(2024, 2, 13), None))
    db_session.flush()
    db_session.add(_subsidy("OTHER_SCHEME", date(2024, 2, 13), None))
    db_session.flush()
    with pytest.raises(IntegrityError):
        db_session.add(_subsidy("CENTRAL_RESIDENTIAL", date(2026, 1, 1), date(2026, 12, 31)))
        db_session.flush()
    db_session.rollback()


def test_quote_snapshot_immutable(db_session: Session):
    owner = make_user(db_session)
    quote = make_quote(db_session, make_lead(db_session, owner), owner)
    with pytest.raises(DBAPIError, match="QUOTE_IMMUTABLE"):
        quote.snapshot = {"options": []}
        db_session.flush()
    db_session.rollback()


def test_quote_valid_and_invalid_transitions(db_session: Session):
    owner = make_user(db_session)
    quote = make_quote(db_session, make_lead(db_session, owner), owner)
    quote.status = QuoteStatus.accepted
    quote.accepted_at = NOW
    quote.accepted_by = owner.id
    quote.selected_kw = Decimal("3")
    db_session.flush()

    with pytest.raises(DBAPIError, match="QUOTE_INVALID_TRANSITION"):
        with db_session.begin_nested():
            db_session.execute(
                text("UPDATE quotes SET status = 'sent' WHERE id = :id"), {"id": quote.id}
            )
    with pytest.raises(DBAPIError, match="QUOTE_FIELD_ALREADY_SET"):
        with db_session.begin_nested():
            db_session.execute(
                text("UPDATE quotes SET accepted_at = now() - interval '1 day' WHERE id = :id"),
                {"id": quote.id},
            )


def test_accept_requires_selection(db_session: Session):
    owner = make_user(db_session)
    quote = make_quote(db_session, make_lead(db_session, owner), owner)
    with pytest.raises(DBAPIError, match="QUOTE_INVALID_TRANSITION"):
        db_session.execute(
            text("UPDATE quotes SET status = 'accepted' WHERE id = :id"), {"id": quote.id}
        )
    db_session.rollback()


def test_superseded_quote_cannot_gain_acceptance(db_session: Session):
    """Review finding 1: lifecycle fields must match status, not just be set once."""
    owner = make_user(db_session)
    quote = make_quote(db_session, make_lead(db_session, owner), owner)
    quote.status = QuoteStatus.superseded
    quote.superseded_at = NOW
    db_session.flush()
    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            db_session.execute(
                text(
                    "UPDATE quotes SET accepted_at = now(), selected_kw = 3, accepted_by = :u "
                    "WHERE id = :id"
                ),
                {"id": quote.id, "u": owner.id},
            )


def test_accepted_quote_cannot_gain_superseded_at(db_session: Session):
    owner = make_user(db_session)
    quote = make_quote(db_session, make_lead(db_session, owner), owner)
    quote.status = QuoteStatus.accepted
    quote.accepted_at = NOW
    quote.accepted_by = owner.id
    quote.selected_kw = Decimal("3")
    db_session.flush()
    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            db_session.execute(
                text("UPDATE quotes SET superseded_at = now() WHERE id = :id"), {"id": quote.id}
            )


def test_insert_accepted_without_selection_rejected(db_session: Session):
    owner = make_user(db_session)
    lead = make_lead(db_session, owner)
    with pytest.raises(IntegrityError):
        db_session.add(
            Quote(
                number="HF-Q-9",
                lead_id=lead.id,
                status=QuoteStatus.accepted,
                priced_on=date(2026, 11, 2),
                snapshot={},
                calc_version="calc-1.0.0",
                created_by=owner.id,
                sent_at=NOW,
            )
        )
        db_session.flush()
    db_session.rollback()


def test_one_open_quote_per_lead(db_session: Session):
    owner = make_user(db_session)
    lead = make_lead(db_session, owner)
    make_quote(db_session, lead, owner, "HF-Q-1")
    with pytest.raises(IntegrityError):
        make_quote(db_session, lead, owner, "HF-Q-2")
    db_session.rollback()


def test_one_accepted_quote_per_lead(db_session: Session):
    """The inbox joins the accepted quote; the database guarantees there is at most one."""
    owner = make_user(db_session)
    lead = make_lead(db_session, owner)

    def accepted(number: str) -> Quote:
        return Quote(
            number=number,
            lead_id=lead.id,
            status=QuoteStatus.accepted,
            priced_on=date(2026, 11, 2),
            snapshot={"options": [{"kw": "3"}]},
            calc_version="calc-1.0.0",
            created_by=owner.id,
            sent_at=NOW,
            accepted_at=NOW,
            accepted_by=owner.id,
            selected_kw=Decimal("3"),
        )

    db_session.add(accepted("HF-Q-1"))
    db_session.flush()
    with pytest.raises(IntegrityError):
        db_session.add(accepted("HF-Q-2"))
        db_session.flush()
    db_session.rollback()
