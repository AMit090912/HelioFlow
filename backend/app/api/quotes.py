"""Quote reads and the homeowner's acceptance (§2 screen 4, §3.8). Staff send from /staff."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_roles
from app.core.errors import ApiError
from app.models import Lead, Quote, User
from app.models.enums import UserRole
from app.schemas.quotes import AcceptIn, QuoteView
from app.services import quotes
from app.services.pdf.quote_pdf import render_quote_pdf

router = APIRouter(prefix="/quotes", tags=["quotes"])


def readable_quote(db: Session, quote_id: uuid.UUID, user: User) -> tuple[Quote, Lead]:
    """Staff read any quote; a homeowner only their own (404 otherwise, §4)."""
    quote = db.get(Quote, quote_id)
    lead = db.get(Lead, quote.lead_id) if quote else None
    if quote is None or lead is None:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    if user.role == UserRole.homeowner and lead.homeowner_id != user.id:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    return quote, lead


def _for(user: User, view: QuoteView) -> QuoteView:
    return quotes.homeowner_view(view) if user.role == UserRole.homeowner else view


@router.get("/{quote_id}", response_model=QuoteView)
def get_quote(
    quote_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> QuoteView:
    return _for(user, quotes.view_of(*readable_quote(db, quote_id, user)))


@router.post("/{quote_id}/accept", response_model=QuoteView)
def accept(
    quote_id: uuid.UUID,
    body: AcceptIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("homeowner")),  # §4: accepting is the homeowner's call
) -> QuoteView:
    quote = quotes.accept_quote(db, quote_id, user, body.selected_kw)
    db.commit()
    return _for(user, quotes.view_of(quote, db.get(Lead, quote.lead_id)))


@router.get("/{quote_id}/pdf")
def quote_pdf(
    quote_id: uuid.UUID,
    lang: Literal["en", "hi", "mr"] | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Rendered from the snapshot on demand, so it is always reproducible (§11). Defaults to
    the homeowner's language, whoever downloads it."""
    quote, lead = readable_quote(db, quote_id, user)
    locale = lang or db.get(User, lead.homeowner_id).preferred_locale.value
    view = quotes.view_of(quote, lead)
    pdf = render_quote_pdf(view, locale)  # sync route: FastAPI runs it in its threadpool
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{quote.number}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )
