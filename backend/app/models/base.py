import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Stamped by the app at insert time (Postgres now() is the *transaction* start, so rows from
    # one transaction would tie); the server default remains for rows inserted by hand.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )


def pg_enum(enum_cls: type[Enum], name: str) -> SAEnum:
    """Native Postgres enum that stores the lower-case `.value`, not the member name."""
    return SAEnum(
        enum_cls, name=name, values_callable=lambda e: [m.value for m in e], validate_strings=True
    )
