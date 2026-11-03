import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import User


class SignupIn(BaseModel):
    # Unknown fields (e.g. "role") are ignored: self sign-up is always a homeowner.
    model_config = ConfigDict(extra="ignore")

    full_name: str = Field(max_length=200)  # rules in app.core.names (NAME_INVALID)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    preferred_locale: Literal["en", "hi", "mr"] = "en"


class LoginIn(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class ProfileIn(BaseModel):
    preferred_locale: Literal["en", "hi", "mr"]


class UserOut(BaseModel):
    id: uuid.UUID
    full_name: str
    role: str
    email: str | None
    phone_masked: str | None
    preferred_locale: str

    @classmethod
    def of(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            full_name=user.full_name,
            role=user.role.value,
            email=user.email,
            phone_masked=f"••••••{user.phone[-4:]}" if user.phone else None,
            preferred_locale=user.preferred_locale.value,
        )
