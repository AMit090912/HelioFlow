"""Manual live check: read the synthetic sample bill with the real Groq and Gemini keys.

Not part of the test suite (it costs API calls). Prints what each provider read, how long it
took and which checks fired. Never prints API keys.
Run:  uv run python scripts/live_bill_check.py
"""

import time
from decimal import Decimal
from pathlib import Path

from app.core.config import get_settings
from app.services.ai import GeminiProvider, GroqProvider, run_chain, sanity_flags
from app.services.ai.validation import suggested_average_units
from app.services.uploads import inspect_pdf, normalise_image, relevant_text_pages

BILLS = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "bills"
EXPECTED = {
    "consumer_number": "410012345678",
    "tariff_category": "LT-I Residential",
    "sanctioned_load_kw": "3",
    "current_units": "340",
    "bill_amount": "3200",
    "fixed_charge": "130",
}


def show(label: str, providers, images=None, text=None) -> None:
    t0 = time.monotonic()
    result = run_chain(providers, images=images, text=text)
    took = time.monotonic() - t0
    print(
        f"\n== {label}: {result.provider or 'NO PROVIDER SUCCEEDED'} / {result.model} "
        f"in {took:.1f}s"
    )
    for a in result.attempts:
        print(
            f"   attempt {a['provider']} {a['model']}: {a['outcome']} {a['error_code'] or ''} "
            f"{a['ms']} ms"
        )
    if result.extraction is None:
        return
    e = result.extraction
    for field, expected in EXPECTED.items():
        read = getattr(e, field)
        value = read.value
        got = (
            format(Decimal(str(value)).normalize(), "f")
            if isinstance(value, (int, float, Decimal))
            else value
        )
        mark = "OK " if str(got) == expected else "XX "
        print(f"   {mark}{field:20} {got!s:22} conf={read.confidence:.2f}  (expected {expected})")
    months = [m.units for m in e.monthly_units.value or []]
    print(f"   history {months}  avg={suggested_average_units(e)}  legibility={e.legibility}")
    print(f"   flags {sanity_flags(e, declared_bill=Decimal('3200')) or 'none'}")


def main() -> None:
    s = get_settings()
    groq = GroqProvider(
        s.groq_api_key, s.groq_vision_model, s.groq_text_model, timeout=s.ai_timeout_seconds
    )
    gemini = GeminiProvider(s.gemini_api_key, s.gemini_model, timeout=s.ai_timeout_seconds)
    photo = normalise_image((BILLS / "clear.jpg").read_bytes()).jpeg
    pdf = (BILLS / "text.pdf").read_bytes()
    info = inspect_pdf(pdf)
    text = "\n\n".join(info.pages_text[i] for i in relevant_text_pages(info))

    show("Groq vision (photo)", [groq], images=[photo])
    show("Groq text (text PDF)", [groq], text=text)
    show("Gemini vision (photo)", [gemini], images=[photo])


if __name__ == "__main__":
    main()
