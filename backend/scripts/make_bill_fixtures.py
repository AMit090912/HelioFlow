"""Generate synthetic electricity-bill fixtures for tests and demos.

Everything here is fictional: "Sample DISCOM" is not a real distribution company, and the
consumer number is made up. The figures follow the brief's sample lead (340 units, ₹3,200).
Run:  uv run python scripts/make_bill_fixtures.py
"""

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "bills"

BILL_LINES = [
    ("SAMPLE DISCOM - Electricity Bill", 44),
    ("Synthetic test bill. Not a real company or customer.", 22),
    ("", 20),
    ("Consumer No: 410012345678", 30),
    ("Name: Sample Customer", 30),
    ("Tariff Category: LT-I Residential", 30),
    ("Sanctioned Load: 3.00 kW", 30),
    ("Bill Month: Oct-2026", 30),
    ("", 20),
    ("Units Consumed (kWh): 340", 34),
    ("Fixed Charges: Rs. 130.00", 30),
    ("Energy Charges: Rs. 2,890.00", 30),
    ("Electricity Duty: Rs. 180.00", 30),
    ("Total Amount Payable: Rs. 3,200.00", 36),
    ("", 20),
    ("Consumption history (units)", 30),
    ("May-26 360   Jun-26 380   Jul-26 310", 28),
    ("Aug-26 320   Sep-26 330   Oct-26 340", 28),
]
COVER_LINES = [
    "Thank you for being a valued customer.",
    "Pay online, at any collection centre, or through your bank.",
    "Keep this page for your records.",
]


def bill_image() -> Image.Image:
    img = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((60, 60, 1180, 1694), outline="black", width=4)
    y = 110
    for text, size in BILL_LINES:
        if text:
            draw.text((110, y), text, fill="black", font=ImageFont.load_default(size=size))
        y += int(size * 1.9)
    return img


def jpeg(img: Image.Image, **kw) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90, **kw)
    return buf.getvalue()


def text_pdf(pages: list[list[str]], image_page: Image.Image | None = None) -> bytes:
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    for lines in pages:
        y = 780
        for line in lines:
            pdf.setFont("Helvetica", 14)
            pdf.drawString(60, y, line)
            y -= 26
        pdf.showPage()
    if image_page is not None:
        pdf.setFont("Helvetica", 12)
        pdf.drawString(60, 800, COVER_LINES[0])
        pdf.drawImage(ImageReader(image_page), 40, 40, width=515, height=728)
        pdf.showPage()
    pdf.save()
    return buf.getvalue()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    clear = bill_image()
    (OUT / "clear.jpg").write_bytes(jpeg(clear))
    (OUT / "blurry.jpg").write_bytes(jpeg(clear.filter(ImageFilter.GaussianBlur(6))))
    (OUT / "dark.jpg").write_bytes(jpeg(ImageEnhance.Brightness(clear).enhance(0.12)))
    tiny = io.BytesIO()
    clear.resize((420, 595)).save(tiny, "PNG")
    (OUT / "tiny.png").write_bytes(tiny.getvalue())
    webp = io.BytesIO()
    clear.save(webp, "WEBP", quality=85)
    (OUT / "bill.webp").write_bytes(webp.getvalue())

    # A phone photo stored sideways with EXIF orientation 6 and a GPS location.
    exif = Image.Exif()
    exif[0x0112] = 6
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2], gps[3], gps[4] = "N", (21.0, 8.0, 46.0), "E", (79.0, 5.0, 18.0)
    (OUT / "rotated_exif.jpg").write_bytes(
        jpeg(clear.transpose(Image.Transpose.ROTATE_90), exif=exif.tobytes())
    )

    bill_text = [text for text, _ in BILL_LINES if text]
    (OUT / "text.pdf").write_bytes(text_pdf([bill_text]))
    (OUT / "multipage.pdf").write_bytes(text_pdf([COVER_LINES, bill_text]))
    # Has a text layer, but only cover text; the bill itself is an image on the page.
    (OUT / "cover_only_text.pdf").write_bytes(text_pdf([], image_page=clear))
    scanned = io.BytesIO()
    clear.save(scanned, "PDF", resolution=150)
    (OUT / "scanned.pdf").write_bytes(scanned.getvalue())

    writer = PdfWriter(clone_from=PdfReader(io.BytesIO((OUT / "text.pdf").read_bytes())))
    writer.encrypt("open-sesame")
    enc = io.BytesIO()
    writer.write(enc)
    (OUT / "encrypted.pdf").write_bytes(enc.getvalue())
    good = (OUT / "text.pdf").read_bytes()
    (OUT / "corrupt.pdf").write_bytes(good[: len(good) // 3])
    (OUT / "fake.jpg").write_bytes(b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 512)
    print("wrote", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
