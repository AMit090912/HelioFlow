"""PDF inspection and routing (§5.2).

Text-based bills go to the AI as text (cheaper, exact); scanned bills are rendered to images.
Only the 1–2 most relevant pages ever leave the server.
"""

import io
import re
from dataclasses import dataclass

import pypdfium2 as pdfium
from pypdf import PdfReader
from pypdf.errors import DependencyError, PyPdfError

from app.services.uploads.errors import UploadError
from app.services.uploads.images import STORE_LONG_SIDE, NormalisedImage, from_pil

MAX_PAGES = 20
MAX_PAGE_POINTS = 14_400  # 200 inches; real bills are A4/Letter (~842 pt)
TEXT_PAGES_SCANNED = 5
MAX_SENT_PAGES = 2
MIN_TEXT_CHARS = 200
RENDER_DPI = 200
BILL_KEYWORDS = re.compile(r"\b(units?|kwh|consumer|sanctioned|tariff)\b", re.IGNORECASE)


@dataclass(frozen=True)
class PdfInfo:
    page_count: int
    pages_text: list[str]  # text of the first TEXT_PAGES_SCANNED pages


def inspect_pdf(data: bytes) -> PdfInfo:
    try:
        reader = PdfReader(io.BytesIO(data))
        # E-bills are often AES-encrypted with an empty user password (owner restrictions only):
        # those open fine. Only a real user password is refused.
        if reader.is_encrypted and not reader.decrypt(""):
            raise UploadError(
                "PDF_ENCRYPTED",
                "This PDF is password-protected. Upload an unlocked copy or a photo.",
            )
        count = len(reader.pages)
        if count > MAX_PAGES:
            raise UploadError("PDF_TOO_MANY_PAGES", f"PDFs can have at most {MAX_PAGES} pages.")
        for page in reader.pages[:MAX_SENT_PAGES]:
            box = page.mediabox
            if max(float(box.width), float(box.height)) > MAX_PAGE_POINTS:
                raise UploadError("PDF_CORRUPT", "This PDF has an impossible page size.")
        texts = [(page.extract_text() or "") for page in reader.pages[:TEXT_PAGES_SCANNED]]
    except UploadError:
        raise
    except (
        PyPdfError,
        DependencyError,
        ValueError,
        KeyError,
        TypeError,
        OSError,
        RecursionError,
    ) as exc:
        raise UploadError("PDF_CORRUPT", "This PDF seems damaged.") from exc
    if count == 0:
        raise UploadError("PDF_CORRUPT", "This PDF has no pages.")
    return PdfInfo(page_count=count, pages_text=texts)


def relevant_text_pages(info: PdfInfo) -> list[int]:
    """Pages with real bill text, best first. Empty means "treat as scanned"."""
    scored = []
    for index, text in enumerate(info.pages_text):
        hits = len(BILL_KEYWORDS.findall(text))
        if len(text.strip()) >= MIN_TEXT_CHARS and hits:
            scored.append((hits, -index, index))
    return sorted(i for *_, i in sorted(scored, reverse=True)[:MAX_SENT_PAGES])


def pages_to_render(info: PdfInfo) -> list[int]:
    return list(range(min(info.page_count, MAX_SENT_PAGES)))


def _scale(page: pdfium.PdfPage) -> float:
    """200 DPI, but never a bitmap larger than STORE_LONG_SIDE: decided *before* rendering, so a
    tiny PDF with a huge page box cannot make pdfium allocate gigabytes."""
    width, height = page.get_size()
    return min(RENDER_DPI / 72, STORE_LONG_SIDE / max(width, height, 1))


def render_pages(data: bytes, pages: list[int]) -> list[NormalisedImage]:
    try:
        doc = pdfium.PdfDocument(data)
        try:
            out = []
            for i in pages:
                page = doc[i]
                if max(page.get_size()) > MAX_PAGE_POINTS:
                    raise UploadError("PDF_CORRUPT", "This PDF has an impossible page size.")
                out.append(from_pil(page.render(scale=_scale(page)).to_pil()))
            return out
        finally:
            doc.close()
    except pdfium.PdfiumError as exc:
        raise UploadError("PDF_CORRUPT", "This PDF could not be rendered.") from exc
