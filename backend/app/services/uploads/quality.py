"""Deterministic photo-quality gate, run before any AI call (§5.3).

Thresholds are assumption A-16, calibrated on the synthetic fixtures
(scripts/make_bill_fixtures.py):
clear bill sharpness ≈ 1964, Gaussian-blurred ≈ 222; dark mean ≈ 29 vs ≈ 248 normal.
A white bill is naturally bright, so "too bright" needs both high brightness and almost no contrast.

Thermal "spot bill" receipts (e.g. TSSPDCL) are long and narrow: a phone photo of one is often only
300–450 px wide yet perfectly readable. A receipt shape (height ≥ 2.2 × width) therefore needs
only a short side of 200 px and a long side of 600 px (A-16, revised twice after real samples:
a sharp 312-px-wide photo was readable). Only true thumbnails are refused here; whether the text
can be read is decided by whether the AI gets the units back.
Sharpness is measured at the photo's own scale, never enlarged: enlarging a narrow receipt to
1,000 px would blur it and fail a sharp photo.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageFilter, ImageStat

MIN_SHORT_SIDE = 700
RECEIPT_ASPECT = 2.2
RECEIPT_MIN_SHORT_SIDE = 200
RECEIPT_MIN_LONG_SIDE = 600
MIN_BRIGHTNESS = 40
WASHED_OUT_BRIGHTNESS = 240
WASHED_OUT_CONTRAST = 10
MIN_SHARPNESS = 600
_MEASURE_WIDTH = 1000  # larger photos are measured at this width so size doesn't skew sharpness


@dataclass(frozen=True)
class Quality:
    ok: bool
    reasons: tuple[str, ...]  # too_small | too_dark | too_bright | blurry
    metrics: dict[str, float]


def check_quality(jpeg: bytes) -> Quality:
    with Image.open(io.BytesIO(jpeg)) as img:
        gray = img.convert("L")
    width, height = gray.size
    scale_to = min(width, _MEASURE_WIDTH)  # shrink big photos; never enlarge small ones
    measured = gray.resize((scale_to, max(1, round(scale_to * height / width))))
    stats = ImageStat.Stat(measured)
    brightness, contrast = stats.mean[0], stats.stddev[0]
    sharpness = ImageStat.Stat(measured.filter(ImageFilter.FIND_EDGES)).var[0]

    reasons = []
    short, long = min(width, height), max(width, height)
    receipt = long >= RECEIPT_ASPECT * short
    if receipt:
        if short < RECEIPT_MIN_SHORT_SIDE or long < RECEIPT_MIN_LONG_SIDE:
            reasons.append("too_small")
    elif short < MIN_SHORT_SIDE:
        reasons.append("too_small")
    if brightness < MIN_BRIGHTNESS:
        reasons.append("too_dark")
    elif brightness > WASHED_OUT_BRIGHTNESS and contrast < WASHED_OUT_CONTRAST:
        reasons.append("too_bright")
    if sharpness < MIN_SHARPNESS and "too_bright" not in reasons:
        reasons.append("blurry")
    metrics = {
        "short_side": float(min(width, height)),
        "brightness": round(brightness, 1),
        "contrast": round(contrast, 1),
        "sharpness": round(sharpness, 1),
    }
    return Quality(ok=not reasons, reasons=tuple(reasons), metrics=metrics)
