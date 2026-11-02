from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_roles
from app.models import Setting, User

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("/settings")
def list_settings(
    db: Session = Depends(get_db), _: User = Depends(require_roles("sales", "admin"))
) -> list[dict]:
    rows = db.execute(select(Setting).order_by(Setting.key)).scalars()
    return [{"key": row.key, "value": row.value} for row in rows]
