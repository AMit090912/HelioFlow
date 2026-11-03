"""Screen 5: the public project status link (§12). No sign-in; rate-limited per IP; the
response carries no personal or financial data. Referrer/robots headers are set for every
/api/public response by the app middleware (errors included)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import ApiError
from app.core.ratelimit import SlidingWindowLimiter, client_ip
from app.services import projects

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/status/{token}")
def project_status(token: str, request: Request, db: Session = Depends(get_db)) -> dict:
    limiter: SlidingWindowLimiter = request.app.state.status_limiter
    key = f"status|{client_ip(request)}"
    if limiter.is_blocked(key):
        raise ApiError(429, "RATE_LIMITED", "Too many requests. Try again in a minute.")
    limiter.record(key)
    return projects.public_status(db, token)
