from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

# hide_parameters: database errors must never write customer values (consumer numbers,
# phones) into logs via the bound parameters (§14).
engine = create_engine(
    get_settings().database_url, pool_pre_ping=True, future=True, hide_parameters=True
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
