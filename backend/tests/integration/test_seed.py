from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import Lead, User
from seed import run

DEMO_PASSWORD = "demo-pass-for-tests"


def test_seed_creates_expected_rows_once(db_session: Session):
    first = run(db_session, DEMO_PASSWORD)
    assert first.created == {
        "users": 5, "settings": 7, "price_rules": 1, "subsidy_rules": 1, "leads": 3,
    }
    second = run(db_session, DEMO_PASSWORD)
    assert sum(second.created.values()) == 0


def test_seed_values_match_brief_and_spec(db_session: Session):
    run(db_session, DEMO_PASSWORD)
    sales = db_session.execute(
        select(User).where(User.email == "sales@helioflow.example")
    ).scalar_one()
    assert verify_password(DEMO_PASSWORD, sales.password_hash)

    ayesha = db_session.execute(select(Lead).where(Lead.code == "LD-30915")).scalar_one()
    assert ayesha.declared_monthly_bill == Decimal("650")
    assert ayesha.score is None  # scoring arrives with the calc engine (M2)
    assert ayesha.seed_note and "Synthetic" in ayesha.seed_note

    rohit = db_session.execute(select(Lead).where(Lead.code == "LD-30902")).scalar_one()
    assert rohit.ownership.value == "tenant"
