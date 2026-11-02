"""Image normalisation: decode safely, apply EXIF orientation, re-encode without metadata (§5.1).

Re-encoding from pixels drops every EXIF/XMP block, including GPS, so a phone photo of a bill
never stores where the customer lives.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from app.services.uploads.errors import UploadError

MAX_PIXELS = 40_000_000  # §5.1: 40 MP. Checked from the header, before any pixels are decoded.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS  # Pillow's own guard only errors above 2× this
STORE_LONG_SIDE = 2500  # what we keep and send to the AI
PREVIEW_LONG_SIDE = 1400  # what the browser shows


@dataclass(frozen=True)
class NormalisedImage:
    jpeg: bytes
    preview_png: bytes
    width: int
    height: int


def _fit(img: Image.Image, long_side: int) -> Image.Image:
    if max(img.size) <= long_side:
        return img
    scale = long_side / max(img.size)
    return img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)


def from_pil(img: Image.Image) -> NormalisedImage:
    clean = _fit(img.convert("RGB"), STORE_LONG_SIDE)
    jpeg = io.BytesIO()
    clean.save(jpeg, "JPEG", quality=88, optimize=True)  # no exif= → no metadata
    preview = io.BytesIO()
    _fit(clean, PREVIEW_LONG_SIDE).save(preview, "PNG", optimize=True)
    return NormalisedImage(jpeg.getvalue(), preview.getvalue(), clean.width, clean.height)


def normalise_image(data: bytes) -> NormalisedImage:
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.width * probe.height > MAX_PIXELS:
                raise UploadError("IMAGE_TOO_LARGE", "This image has too many pixels.")
            probe.verify()  # structural check before decoding pixels
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            upright = ImageOps.exif_transpose(img)
            return from_pil(upright)
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise UploadError("IMAGE_UNREADABLE", "This image could not be opened.") from exc
