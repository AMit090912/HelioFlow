"""Deterministic photo-quality gate, run before any AI call (§5.3).

Thresholds are assumption A-16, calibrated on the synthetic fixtures
(scripts/make_bill_fixtures.py):
clear bill sharpness ≈ 1964, Gaussian-blurred ≈ 222; dark mean ≈ 29 vs ≈ 248 normal.
A white bill is naturally bright, so "too bright" needs both high brightness and almost no contrast.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageFilter, ImageStat

MIN_SHORT_SIDE = 700
MIN_BRIGHTNESS = 40
WASHED_OUT_BRIGHTNESS = 240
WASHED_OUT_CONTRAST = 10
MIN_SHARPNESS = 600
_MEASURE_WIDTH = 1000  # sharpness is measured at a fixed scale so image size doesn't skew it


@dataclass(frozen=True)
class Quality:
    ok: bool
    reasons: tuple[str, ...]  # too_small | too_dark | too_bright | blurry
    metrics: dict[str, float]


def check_quality(jpeg: bytes) -> Quality:
    with Image.open(io.BytesIO(jpeg)) as img:
        gray = img.convert("L")
    width, height = gray.size
    measured = gray.resize((_MEASURE_WIDTH, max(1, round(_MEASURE_WIDTH * height / width))))
    stats = ImageStat.Stat(measured)
    brightness, contrast = stats.mean[0], stats.stddev[0]
    sharpness = ImageStat.Stat(measured.filter(ImageFilter.FIND_EDGES)).var[0]

    reasons = []
    if min(width, height) < MIN_SHORT_SIDE:
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
