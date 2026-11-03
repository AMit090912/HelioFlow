from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import SESSION_COOKIE, ApiError
from app.core.ratelimit import SlidingWindowLimiter, client_ip
from app.core.security import (
    create_session_token,
    hash_password,
    is_common_password,
    normalize_email,
    normalize_phone,
    verify_password,
)
from app.models import User
from app.models.enums import Locale, UserRole
from app.schemas.auth import LoginIn, ProfileIn, SignupIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

# Verified against when the user does not exist, so both paths cost one argon2 check.
_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")


def _set_session(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user.id, user.role.value),
        max_age=settings.jwt_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _clean_email(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    try:
        return normalize_email(validate_email(raw.strip(), check_deliverability=False).normalized)
    except EmailNotValidError as exc:
        raise ApiError(422, "EMAIL_INVALID", "Enter a valid email address.") from exc


def _clean_phone(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    phone = normalize_phone(raw)
    if phone is None:
        raise ApiError(422, "PHONE_INVALID", "Enter a 10-digit Indian mobile number.")
    return phone


@router.post("/signup", status_code=201, response_model=UserOut)
def signup(body: SignupIn, response: Response, db: Session = Depends(get_db)) -> UserOut:
    email = _clean_email(body.email)
    phone = _clean_phone(body.phone)
    if email is None and phone is None:
        raise ApiError(422, "IDENTIFIER_REQUIRED", "Enter an email or a mobile number.")
    if is_common_password(body.password):
        raise ApiError(422, "PASSWORD_TOO_COMMON", "Choose a less common password.")

    if _identity_taken(db, email, phone):
        raise _account_exists()

    user = User(
        role=UserRole.homeowner,
        full_name=body.full_name.strip(),
        email=email,
        phone=phone,
        password_hash=hash_password(body.password),
        preferred_locale=Locale(body.preferred_locale),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:  # concurrent signup won the race; the unique index decides
        db.rollback()
        raise _account_exists() from exc
    _set_session(response, user)
    return UserOut.of(user)


def _identity_taken(db: Session, email: str | None, phone: str | None) -> bool:
    same_identity = []
    if email:
        same_identity.append(User.email == email)
    if phone:
        same_identity.append(User.phone == phone)
    return db.execute(select(User.id).where(or_(*same_identity))).first() is not None


def _account_exists() -> ApiError:
    return ApiError(409, "ACCOUNT_EXISTS", "An account with these details already exists.")


@router.post("/login", response_model=UserOut)
def login(
    body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)
) -> UserOut:
    phone = normalize_phone(body.identifier)
    identifier = phone or normalize_email(body.identifier)
    limiter: SlidingWindowLimiter = request.app.state.login_limiter
    # Per caller and account: an attacker failing logins cannot lock the real user out.
    key = f"{client_ip(request)}|{identifier}"
    if limiter.is_blocked(key):
        raise ApiError(429, "RATE_LIMITED", "Too many attempts. Try again in a minute.")

    column = User.phone if phone else User.email
    user = db.execute(select(User).where(column == identifier)).scalar_one_or_none()
    password_ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not password_ok or not user.is_active:
        limiter.record(key)
        raise ApiError(401, "INVALID_CREDENTIALS", "Those details don't match an account.")

    limiter.reset(key)
    _set_session(response, user)
    return UserOut.of(user)


@router.post("/logout", status_code=204)
def logout(response: Response) -> Response:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.of(user)


@router.patch("/me", response_model=UserOut)
def update_me(
    body: ProfileIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> UserOut:
    """The language choice is saved so messages and PDFs follow it (§2 Languages)."""
    user.preferred_locale = Locale(body.preferred_locale)
    db.commit()
    return UserOut.of(user)
