"""AI bill extraction: schema, provider requests, fallback chain, sanity checks (§6)."""

import json
from decimal import Decimal as D

import httpx
import pytest

from app.services.ai import (
    PROMPT_VERSION,
    BillExtraction,
    GeminiProvider,
    GroqProvider,
    ProviderError,
    run_chain,
    sanity_flags,
    suggested_average_units,
)

GOOD = {
    "is_electricity_bill": True,
    "legibility": "good",
    "consumer_number": {"value": "410012345678", "confidence": 0.97},
    "tariff_category": {"value": "LT-I Residential", "confidence": 0.95},
    "sanctioned_load_kw": {"value": 3.0, "confidence": 0.93},
    "monthly_units": {
        "value": [
            {"month": f"2026-{m:02d}", "units": u}
            for m, u in [(5, 360), (6, 380), (7, 310), (8, 320), (9, 330), (10, 340)]
        ],
        "confidence": 0.9,
    },
    "current_units": {"value": 340, "confidence": 0.96},
    "bill_amount": {"value": 3200, "confidence": 0.96},
    "fixed_charge": {"value": 130, "confidence": 0.8},
}


# --- Schema ---


def test_schema_accepts_a_good_reading():
    e = BillExtraction.model_validate(GOOD)
    assert e.sanctioned_load_kw.value == D("3.0")
    assert e.current_units.value == 340


def test_schema_rejects_wrong_types():
    """Review Focus 3: valid JSON with wrong types is an invalid response."""
    from pydantic import ValidationError

    bad = {**GOOD, "current_units": {"value": "three hundred", "confidence": 0.9}}
    with pytest.raises(ValidationError):
        BillExtraction.model_validate(bad)


def test_missing_values_are_null_not_guessed():
    e = BillExtraction.model_validate({**GOOD, "fixed_charge": {"value": None, "confidence": 0}})
    assert e.fixed_charge.value is None


# --- Provider request shapes (no network) ---


def _capture(response_json, status=200, headers=None):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return httpx.Response(status, json=response_json, headers=headers or {})

    return seen, httpx.MockTransport(handler)


def test_groq_vision_request_uses_json_mode_and_image_data_url():
    reply = {"choices": [{"message": {"content": json.dumps(GOOD)}}]}
    seen, transport = _capture(reply)
    groq = GroqProvider("k-123", "vision-m", "text-m", timeout=5, transport=transport)
    out = groq.extract(images=[b"\xff\xd8\xffjpeg"], text=None)
    body = json.loads(seen["request"].content)
    assert seen["request"].headers["authorization"] == "Bearer k-123"
    assert "user-agent" in seen["request"].headers
    assert body["model"] == "vision-m" and body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    parts = body["messages"][1]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert out["legibility"] == "good" and groq.last_model == "vision-m"


def test_groq_text_request_uses_the_text_model_and_plain_string():
    reply = {
        "choices": [
            {"message": {"content": "<think>hmm</think>```json\n" + json.dumps(GOOD) + "\n```"}}
        ]
    }
    seen, transport = _capture(reply)
    groq = GroqProvider("k", "vision-m", "text-m", timeout=5, transport=transport)
    out = groq.extract(images=None, text="Units Consumed: 340")
    body = json.loads(seen["request"].content)
    assert body["model"] == "text-m"
    assert isinstance(body["messages"][1]["content"], str)
    assert out["current_units"]["value"] == 340  # think-block and code fence stripped


def test_gemini_key_goes_in_a_header_never_the_url():
    reply = {"candidates": [{"content": {"parts": [{"text": json.dumps(GOOD)}]}}]}
    seen, transport = _capture(reply)
    gem = GeminiProvider("g-secret", "gemini-x", timeout=5, transport=transport)
    gem.extract(images=[b"\xff\xd8\xffjpeg"], text=None)
    req = seen["request"]
    assert "g-secret" not in str(req.url)
    assert req.headers["x-goog-api-key"] == "g-secret"
    body = json.loads(req.content)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["contents"][0]["parts"][1]["inline_data"]["mime_type"] == "image/jpeg"


@pytest.mark.parametrize(
    ("status", "kind"),
    [(429, "rate_limited"), (503, "server"), (401, "auth"), (400, "bad_request")],
)
def test_http_errors_map_to_kinds(status, kind):
    _, transport = _capture(
        {"error": {"message": "x"}}, status=status, headers={"retry-after": "2"}
    )
    with pytest.raises(ProviderError) as err:
        GroqProvider("k", "v", "t", timeout=5, transport=transport).extract(images=None, text="x")
    assert err.value.kind == kind
    if kind == "rate_limited":
        assert err.value.retry_after == 2.0


def test_non_json_reply_is_invalid_response():
    _, transport = _capture({"choices": [{"message": {"content": "Sorry, I can't read that."}}]})
    with pytest.raises(ProviderError) as err:
        GroqProvider("k", "v", "t", timeout=5, transport=transport).extract(images=None, text="x")
    assert err.value.kind == "invalid_response"


def test_timeout_maps_to_timeout():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderError) as err:
        GeminiProvider("k", "m", timeout=5, transport=httpx.MockTransport(handler)).extract(
            images=None, text="x"
        )
    assert err.value.kind == "timeout"


# --- Chain ---


class Scripted:
    def __init__(self, name, *outcomes):
        self.name, self.last_model, self.outcomes, self.calls = (
            name,
            f"{name}-model",
            list(outcomes),
            0,
        )

    def extract(self, *, images, text):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def chain(*providers):
    sleeps = []
    result = run_chain(list(providers), images=[b"img"], text=None, sleep=sleeps.append)
    return result, sleeps


def test_groq_success_stops_the_chain():
    groq, gem = Scripted("groq", GOOD), Scripted("gemini", GOOD)
    result, _ = chain(groq, gem)
    assert result.provider == "groq" and result.model == "groq-model"
    assert gem.calls == 0
    assert result.attempts[0]["outcome"] == "ok"
    assert result.attempts[0]["prompt_version"] == PROMPT_VERSION


def test_rate_limit_retries_once_then_falls_back():
    groq = Scripted(
        "groq", ProviderError("rate_limited", 429, 9.0), ProviderError("rate_limited", 429, 1.0)
    )
    gem = Scripted("gemini", GOOD)
    result, sleeps = chain(groq, gem)
    assert groq.calls == 2 and result.provider == "gemini"
    assert sleeps == [5.0]  # Retry-After honoured but capped at 5 s
    assert [a["error_code"] for a in result.attempts] == ["rate_limited", "rate_limited", None]


def test_invalid_json_moves_straight_to_next_provider():
    groq = Scripted("groq", ProviderError("invalid_response"))
    gem = Scripted("gemini", GOOD)
    result, sleeps = chain(groq, gem)
    assert groq.calls == 1 and sleeps == [] and result.provider == "gemini"


def test_wrong_types_count_as_invalid_and_fall_back():
    groq = Scripted("groq", {**GOOD, "bill_amount": {"value": "lots", "confidence": 1}})
    gem = Scripted("gemini", GOOD)
    result, _ = chain(groq, gem)
    assert result.provider == "gemini"
    assert result.attempts[0]["error_code"] == "invalid_response"


def test_both_failing_returns_no_extraction_and_keeps_every_attempt():
    groq = Scripted("groq", ProviderError("auth", 401))
    gem = Scripted("gemini", ProviderError("timeout"), ProviderError("timeout"))
    result, _ = chain(groq, gem)
    assert result.extraction is None and result.provider is None
    assert [(a["provider"], a["error_code"]) for a in result.attempts] == [
        ("groq", "auth"),
        ("gemini", "timeout"),
        ("gemini", "timeout"),
    ]
    assert all("ms" in a and "started_at" in a for a in result.attempts)


def test_chain_stops_at_its_deadline():
    """Review fix 5: the whole chain has a hard time budget, below the stale threshold."""
    now = {"t": 0.0}

    class Slow(Scripted):
        def extract(self, *, images, text):
            now["t"] += 60  # each call takes a minute
            return super().extract(images=images, text=text)

    groq = Slow("groq", ProviderError("timeout"), ProviderError("timeout"))
    gem = Slow("gemini", GOOD)
    result = run_chain(
        [groq, gem],
        images=[b"x"],
        text=None,
        sleep=lambda s: None,
        budget_seconds=90,
        clock=lambda: now["t"],
    )
    assert result.extraction is None and gem.calls == 0
    assert result.attempts[-1]["error_code"] == "deadline_exceeded"


def test_unexpected_provider_exception_falls_back_instead_of_crashing():
    groq = Scripted("groq", RuntimeError("decoder exploded"))
    gem = Scripted("gemini", GOOD)
    result, _ = chain(groq, gem)
    assert result.provider == "gemini"
    assert result.attempts[0]["error_code"] == "unexpected"


def test_no_providers_configured_is_a_clean_failure():
    result, _ = chain()
    assert result.extraction is None and result.attempts == []


# --- Demo mode (§6.5): only the synthetic sample bill is "read" ---


def test_demo_reads_only_the_synthetic_sample_bill():
    import hashlib

    from app.services.ai.demo import SAMPLES_DIR, DemoProvider

    sample_sha = hashlib.sha256((SAMPLES_DIR / "sample-bill.jpg").read_bytes()).hexdigest()
    known = DemoProvider(sample_sha).extract(images=[b"x"], text=None)
    assert BillExtraction.model_validate(known).current_units.value == 340
    other = DemoProvider("0" * 64).extract(images=[b"x"], text=None)
    assert other["legibility"] == "poor"
    # Only the exact sample file counts — typing "SAMPLE DISCOM" into any PDF is not enough.
    by_text = DemoProvider("0" * 64).extract(images=None, text="SAMPLE DISCOM bill")
    assert by_text["legibility"] == "poor"


# --- Sanity checks (§6.3) and average units ---


def extraction(**overrides):
    return BillExtraction.model_validate({**GOOD, **overrides})


def test_clean_reading_has_no_flags():
    assert sanity_flags(extraction(), declared_bill=D("3200")) == {}


def test_out_of_range_and_unusual_values_are_flagged():
    flags = sanity_flags(
        extraction(
            sanctioned_load_kw={"value": 250, "confidence": 0.9},
            consumer_number={"value": "AB12", "confidence": 0.9},
            current_units={"value": 9000, "confidence": 0.9},
        ),
        declared_bill=D("3200"),
    )
    assert "out_of_range" in flags["sanctioned_load_kw"]
    assert "format_unusual" in flags["consumer_number"]
    assert "out_of_range" in flags["current_units"]


def test_bill_differing_from_declared_is_flagged():
    flags = sanity_flags(extraction(), declared_bill=D("2000"))
    assert flags["bill_amount"] == ["differs_from_declared"]


def test_implied_rate_outside_two_to_twenty_five_is_flagged():
    flags = sanity_flags(
        extraction(bill_amount={"value": 340, "confidence": 0.9}), declared_bill=D("340")
    )
    assert "rate_unusual" in flags["bill_amount"]


def test_low_confidence_is_highlighted():
    flags = sanity_flags(
        extraction(tariff_category={"value": "LT-I", "confidence": 0.4}), declared_bill=D("3200")
    )
    assert flags["tariff_category"] == ["low_confidence"]


def test_document_level_problems_are_flagged():
    flags = sanity_flags(
        extraction(is_electricity_bill=False, legibility="poor"), declared_bill=None
    )
    assert set(flags["document"]) == {"not_electricity_bill", "legibility_poor"}


def test_average_uses_history_when_three_or_more_months():
    assert suggested_average_units(extraction()) == (D("340.00"), "history_mean")


def test_average_falls_back_to_current_month():
    e = extraction(monthly_units={"value": [{"month": "2026-10", "units": 340}], "confidence": 0.9})
    assert suggested_average_units(e) == (D("340"), "current_month")


def test_average_unknown_when_nothing_was_read():
    e = extraction(
        monthly_units={"value": None, "confidence": 0},
        current_units={"value": None, "confidence": 0},
    )
    assert suggested_average_units(e) == (None, None)


def test_an_impossible_month_is_left_out_of_the_average():
    """A misread history month (34,000 units) must not drag the suggestion to 8,747 units, and is
    still flagged so the person checks the bill."""
    months = [(7, 340), (8, 320), (9, 34000), (10, 330)]
    e = extraction(
        monthly_units={
            "value": [{"month": f"2026-{m:02d}", "units": u} for m, u in months],
            "confidence": 0.9,
        }
    )
    assert suggested_average_units(e) == (D("330.00"), "history_mean")
    assert "out_of_range" in sanity_flags(e, declared_bill=None)["monthly_units"]
