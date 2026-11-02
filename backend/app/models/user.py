from sqlalchemy import Boolean, CheckConstraint, Text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, pg_enum
from app.models.enums import Locale, UserRole


class User(IdMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email IS NOT NULL OR phone IS NOT NULL", name="email_or_phone"),
        CheckConstraint("phone IS NULL OR phone ~ '^[6-9][0-9]{9}$'", name="phone_format"),
    )

    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"), nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(CITEXT, unique=True)
    phone: Mapped[str | None] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    preferred_locale: Mapped[Locale] = mapped_column(
        pg_enum(Locale, "locale"), nullable=False, default=Locale.en, server_default="en"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
