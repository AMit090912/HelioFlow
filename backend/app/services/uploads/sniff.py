"""File type by content (magic bytes), never by extension or Content-Type (§5.1)."""

from typing import Literal

from app.services.uploads.errors import UploadError

Kind = Literal["jpeg", "png", "webp", "pdf"]


def sniff(data: bytes) -> Kind:
    if not data:
        raise UploadError("FILE_EMPTY", "The file is empty.")
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    raise UploadError("FILE_TYPE_UNSUPPORTED", "We accept PDF, JPG, PNG or WebP.", status=415)


def check_size(data: bytes, max_mb: int) -> None:
    if len(data) > max_mb * 1024 * 1024:
        raise UploadError("FILE_TOO_LARGE", f"This file is larger than {max_mb} MB.", status=413)
