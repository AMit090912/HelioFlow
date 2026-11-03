"""One-click demo sign-in: try the app as a new homeowner, a returning homeowner, sales or admin
without typing anything. For local testing and for reviewers of a deployed demo.

Only available when DEMO_LOGINS=true (off by default, everywhere). No password reaches the
browser: the server issues the session directly. "New homeowner" creates a throwaway account
each time, so every run of the journey starts clean.
"""

import secrets
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import _set_session
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import ApiError
from app.core.ratelimit import SlidingWindowLimiter, client_ip
from app.core.security import hash_password
from app.models import User
from app.models.enums import Locale, UserRole
from app.schemas.auth import UserOut
from seed import data as seed_data

router = APIRouter(prefix="/auth", tags=["demo"])

DemoAs = Literal["new_homeowner", "homeowner", "sales", "admin"]
ACCOUNTS: list[dict[str, str]] = [
    {"as": "new_homeowner", "label": "New homeowner (fresh start)"},
    {"as": "homeowner", "label": "Demo homeowner (keeps progress)"},
    {"as": "sales", "label": "Sales"},
    {"as": "admin", "label": "Admin"},
]
DEMO_HOMEOWNER_EMAIL = "demo.homeowner@helioflow.example"
STAFF_EMAIL = {s["role"]: s["email"] for s in seed_data.STAFF}


def demo_logins_enabled() -> bool:
    return get_settings().demo_logins is True


class DemoLoginIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    as_: DemoAs = Field(alias="as")  # "as" is a Python keyword
    locale: Literal["en", "hi", "mr"] = "en"


def _homeowner(db: Session, email: str, name: str, locale: str) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        user = User(
            role=UserRole.homeowner,
            full_name=name,
            email=email,
            # Nobody knows this password: demo homeowners are reached only through this button.
            password_hash=hash_password(secrets.token_urlsafe(24)),
            preferred_locale=Locale(locale),
        )
        db.add(user)
        db.commit()
    return user


@router.get("/demo-logins")
def list_demo_logins() -> dict:
    enabled = demo_logins_enabled()
    return {"enabled": enabled, "accounts": ACCOUNTS if enabled else []}


@router.post("/demo-login", response_model=UserOut)
def demo_login(
    body: DemoLoginIn, request: Request, response: Response, db: Session = Depends(get_db)
) -> UserOut:
    if not demo_logins_enabled():
        raise ApiError(404, "NOT_FOUND", "Not found.")
    limiter: SlidingWindowLimiter = request.app.state.demo_limiter
    key = f"demo|{client_ip(request)}"
    if limiter.is_blocked(key):
        raise ApiError(429, "RATE_LIMITED", "Too many demo sign-ins. Try again later.")
    limiter.record(key)

    if body.as_ == "new_homeowner":
        tag = secrets.token_hex(3)
        user = _homeowner(db, f"tester-{tag}@demo.helioflow.example", "Test Homeowner", body.locale)
    elif body.as_ == "homeowner":
        user = _homeowner(db, DEMO_HOMEOWNER_EMAIL, "Demo Homeowner", body.locale)
    else:
        user = db.execute(
            select(User).where(User.email == STAFF_EMAIL[body.as_])
        ).scalar_one_or_none()
        if user is None:
            raise ApiError(409, "DEMO_NOT_SEEDED", "Run the seed first: uv run python -m seed.")
    _set_session(response, user)
    return UserOut.of(user)
