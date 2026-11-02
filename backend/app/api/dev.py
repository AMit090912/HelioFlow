"""Development-only endpoints. Never mounted when ENV=production."""

from fastapi import APIRouter, Depends, UploadFile

from app.core.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/upload-probe")
async def upload_probe(file: UploadFile, _: User = Depends(get_current_user)) -> dict:
    """Counts bytes received, to check proxy body limits end to end (ARCHITECTURE Q-9)."""
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
    return {"received_bytes": total}
