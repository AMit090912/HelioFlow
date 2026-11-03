"""Upload acceptance gate, normalisation, PDF routing and photo quality (ARCHITECTURE §5)."""

import io
from pathlib import Path

import pytest
from PIL import Image

from app.services.uploads import (
    UploadError,
    check_quality,
    check_size,
    inspect_pdf,
    normalise_image,
    relevant_text_pages,
    render_pages,
    sniff,
)

BILLS = Path(__file__).resolve().parents[2] / "fixtures" / "bills"


def fixture(name: str) -> bytes:
    return (BILLS / name).read_bytes()


def code_of(fn, *args) -> str:
    with pytest.raises(UploadError) as err:
        fn(*args)
    return err.value.code


# --- Signature, not extension ---


@pytest.mark.parametrize(
    ("name", "kind"),
    [("clear.jpg", "jpeg"), ("tiny.png", "png"), ("bill.webp", "webp"), ("text.pdf", "pdf")],
)
def test_sniff_reads_magic_bytes(name, kind):
    assert sniff(fixture(name)) == kind


def test_renamed_executable_is_rejected():
    assert code_of(sniff, fixture("fake.jpg")) == "FILE_TYPE_UNSUPPORTED"


def test_empty_file_is_rejected():
    assert code_of(sniff, b"") == "FILE_EMPTY"


def test_size_limit_is_enforced():
    check_size(b"x" * (10 * 1024 * 1024), max_mb=10)
    assert code_of(check_size, b"x" * (10 * 1024 * 1024 + 1), 10) == "FILE_TOO_LARGE"


# --- Images: re-encoded, upright, metadata gone ---


def test_image_is_reencoded_without_metadata():
    out = normalise_image(fixture("rotated_exif.jpg"))
    img = Image.open(io.BytesIO(out.jpeg))
    assert img.getexif() == {}  # orientation and GPS gone
    assert (out.width, out.height) == (1240, 1754)  # upright: portrait, not landscape


def test_preview_is_a_png():
    out = normalise_image(fixture("clear.jpg"))
    assert out.preview_png.startswith(b"\x89PNG")


def test_webp_is_accepted_and_converted_to_jpeg():
    assert normalise_image(fixture("bill.webp")).jpeg.startswith(b"\xff\xd8\xff")


def test_truncated_image_is_unreadable():
    broken = fixture("clear.jpg")[:2000]
    assert code_of(normalise_image, broken) == "IMAGE_UNREADABLE"


# --- PDFs ---


def test_text_pdf_routes_to_its_bill_page():
    info = inspect_pdf(fixture("text.pdf"))
    assert info.page_count == 1
    assert relevant_text_pages(info) == [0]
    assert "Sanctioned Load" in info.pages_text[0]


def test_multipage_pdf_picks_the_bill_page_not_the_cover():
    info = inspect_pdf(fixture("multipage.pdf"))
    assert info.page_count == 2
    assert relevant_text_pages(info) == [1]


def test_text_layer_without_bill_keywords_is_not_text_based():
    """Review Focus 2: cover text only → render the page for vision, don't send empty text."""
    info = inspect_pdf(fixture("cover_only_text.pdf"))
    assert info.pages_text[0].strip()  # there is some text
    assert relevant_text_pages(info) == []


def test_scanned_pdf_has_no_usable_text_and_renders():
    info = inspect_pdf(fixture("scanned.pdf"))
    assert relevant_text_pages(info) == []
    pages = render_pages(fixture("scanned.pdf"), [0])
    assert len(pages) == 1
    assert max(pages[0].width, pages[0].height) <= 2500
    assert check_quality(pages[0].jpeg).ok


def test_encrypted_pdf_is_rejected():
    assert code_of(inspect_pdf, fixture("encrypted.pdf")) == "PDF_ENCRYPTED"


def test_corrupt_pdf_is_rejected():
    assert code_of(inspect_pdf, fixture("corrupt.pdf")) == "PDF_CORRUPT"


def test_pdf_with_too_many_pages_is_rejected():
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(21):
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    assert code_of(inspect_pdf, buf.getvalue()) == "PDF_TOO_MANY_PAGES"


# --- Hostile inputs (review fixes 1, 2, 8) ---


def _blank_pdf(width_pt: float, height_pt: float) -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=width_pt, height=height_pt)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_huge_pdf_page_renders_at_capped_size_not_full_dpi():
    """A 6000×6000 pt page must not allocate a 16,000 px bitmap before downscaling."""
    pages = render_pages(_blank_pdf(6000, 6000), [0])
    assert max(pages[0].width, pages[0].height) <= 2500


def test_absurd_pdf_page_size_is_rejected():
    assert code_of(inspect_pdf, _blank_pdf(15000, 15000)) == "PDF_CORRUPT"


def test_image_over_40_megapixels_is_rejected_before_decoding():
    big = Image.new("L", (9000, 5000))  # 45 MP, compresses to a tiny PNG
    buf = io.BytesIO()
    big.save(buf, "PNG")
    assert len(buf.getvalue()) < 500_000
    assert code_of(normalise_image, buf.getvalue()) == "IMAGE_TOO_LARGE"


def test_aes_pdf_with_empty_user_password_is_readable():
    """Utility e-bills are often AES-encrypted with owner restrictions only."""
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(fixture("text.pdf"))))
    writer.encrypt(user_password="", owner_password="owner-only", algorithm="AES-256")
    buf = io.BytesIO()
    writer.write(buf)
    info = inspect_pdf(buf.getvalue())
    assert relevant_text_pages(info) == [0]


# --- Photo quality (A-16, calibrated on these fixtures) ---


def test_clear_photo_passes():
    q = check_quality(normalise_image(fixture("clear.jpg")).jpeg)
    assert q.ok and q.reasons == ()


@pytest.mark.parametrize(
    ("name", "reason"),
    [("blurry.jpg", "blurry"), ("dark.jpg", "too_dark"), ("tiny.png", "too_small")],
)
def test_poor_photos_are_rejected_with_a_reason(name, reason):
    q = check_quality(normalise_image(fixture(name)).jpeg)
    assert not q.ok
    assert reason in q.reasons
    assert set(q.metrics) >= {"short_side", "brightness", "contrast", "sharpness"}


def test_washed_out_photo_is_too_bright():
    blank = Image.new("RGB", (1240, 1754), (252, 252, 252))
    buf = io.BytesIO()
    blank.save(buf, "JPEG")
    assert "too_bright" in check_quality(buf.getvalue()).reasons


# --- Narrow thermal "spot bill" receipts (A-16 revised) ---


def _receipt(width=360, height=1100, blur=0.0) -> bytes:
    from PIL import ImageDraw, ImageFilter

    img = Image.new("RGB", (width, height), (232, 232, 236))
    draw = ImageDraw.Draw(img)
    for row, y in enumerate(range(20, height - 20, 22)):
        draw.text(
            (14, y), f"UNITS: {row * 7 % 900}   DAYS: {30 + row % 64}  KWH", fill=(60, 50, 120)
        )
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def test_narrow_sharp_receipt_passes():
    q = check_quality(normalise_image(_receipt()).jpeg)
    assert q.ok, q


def test_blurred_receipt_is_still_blurry():
    q = check_quality(normalise_image(_receipt(blur=2.5)).jpeg)
    assert "blurry" in q.reasons


def test_small_squat_image_is_still_too_small():
    q = check_quality(normalise_image(_receipt(width=360, height=500)).jpeg)
    assert "too_small" in q.reasons


def test_narrow_sharp_receipt_photo_like_the_users_passes():
    """User report: a clear 312-px-wide receipt photo (sharpness 7,526) was refused as too small."""
    q = check_quality(normalise_image(_receipt(width=312, height=1000)).jpeg)
    assert q.ok, q
    assert check_quality(normalise_image(_receipt(width=274, height=900)).jpeg).ok


def test_thumbnail_receipt_is_still_too_small():
    q = check_quality(normalise_image(_receipt(width=150, height=480)).jpeg)
    assert "too_small" in q.reasons
