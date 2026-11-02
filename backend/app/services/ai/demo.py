"""AI_MODE=demo: a clearly labelled stand-in that only "reads" the synthetic sample bill (§6.5).

It never pretends to read an arbitrary upload: any other file comes back unreadable, and every
reading made in demo mode is marked is_demo in the API and UI.
"""

import hashlib
from pathlib import Path
from typing import Any

SAMPLES_DIR = Path(__file__).with_name("samples")


def _fingerprints() -> frozenset[str]:
    if not SAMPLES_DIR.is_dir():
        return frozenset()
    return frozenset(hashlib.sha256(p.read_bytes()).hexdigest() for p in SAMPLES_DIR.iterdir())


SAMPLE_FINGERPRINTS = _fingerprints()

SAMPLE_BILL_READING: dict[str, Any] = {
    "is_electricity_bill": True,
    "legibility": "good",
    "consumer_number": {"value": "410012345678", "confidence": 0.97},
    "tariff_category": {"value": "LT-I Residential", "confidence": 0.95},
    "sanctioned_load_kw": {"value": 3.0, "confidence": 0.94},
    "monthly_units": {
        "value": [
            {"month": "2026-05", "units": 360},
            {"month": "2026-06", "units": 380},
            {"month": "2026-07", "units": 310},
            {"month": "2026-08", "units": 320},
            {"month": "2026-09", "units": 330},
            {"month": "2026-10", "units": 340},
        ],
        "confidence": 0.9,
    },
    "current_units": {"value": 340, "confidence": 0.96},
    "bill_amount": {"value": 3200, "confidence": 0.96},
    "fixed_charge": {"value": 130, "confidence": 0.85},
}
UNREADABLE: dict[str, Any] = {"is_electricity_bill": False, "legibility": "poor"}


class DemoProvider:
    name = "demo"

    def __init__(self, upload_sha256: str):
        self.last_model: str | None = "demo-fixture"
        self._is_sample = upload_sha256 in SAMPLE_FINGERPRINTS

    def extract(self, *, images: list[bytes] | None, text: str | None) -> dict[str, Any]:
        # Only the exact sample file (by hash) is "read"; text content is never trusted for this.
        return SAMPLE_BILL_READING if self._is_sample else UNREADABLE
