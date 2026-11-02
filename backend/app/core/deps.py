"""Request dependencies: current user, role checks and object-level ownership (§4)."""

import uuid
from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import SESSION_COOKIE, ApiError
from app.core.security import decode_session_token
from app.models import User
from app.models.enums import UserRole


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise ApiError(401, "NOT_AUTHENTICATED", "Please sign in.")
    claims = decode_session_token(token)
    user = db.get(User, claims.user_id) if claims else None
    if user is None or not user.is_active:
        raise ApiError(401, "NOT_AUTHENTICATED", "Please sign in.", clear_session=True)
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    allowed = {UserRole(r) for r in roles}

    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise ApiError(403, "FORBIDDEN", "You do not have access to this.")
        return user

    return _check


def get_owned_or_404[T](db: Session, model: type[T], obj_id: uuid.UUID, user: User) -> T:
    """Load a record; homeowners only ever see their own (404, never 403, to avoid leaking
    existence). Models must expose `homeowner_id` directly."""
    obj = db.get(model, obj_id)
    if obj is None:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    if user.role == UserRole.homeowner and getattr(obj, "homeowner_id", None) != user.id:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    return obj
