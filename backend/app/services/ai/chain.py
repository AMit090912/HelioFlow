"""Provider fallback chain (§6.2): Groq → Gemini → (caller falls back to manual entry).

One retry per provider for transient errors (429/5xx/timeout/network), honouring Retry-After up to
5 s. An invalid or wrongly-typed reply goes straight to the next provider. Every attempt is
recorded so a reviewer can see exactly what happened to a bill.
"""

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from app.services.ai.prompt import PROMPT_VERSION
from app.services.ai.providers import RETRYABLE, Provider, ProviderError
from app.services.ai.schema import BillExtraction

MAX_RETRY_WAIT = 5.0
CHAIN_BUDGET_SECONDS = 75.0  # whole chain; the stale sweep fires at 120 s
log = logging.getLogger("helio.ai")


@dataclass
class ChainResult:
    extraction: BillExtraction | None
    raw: dict[str, Any] | None = None
    provider: str | None = None
    model: str | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)


def run_chain(
    providers: Sequence[Provider],
    *,
    images: list[bytes] | None,
    text: str | None,
    sleep: Callable[[float], None] = time.sleep,
    budget_seconds: float = CHAIN_BUDGET_SECONDS,
    clock: Callable[[], float] = time.monotonic,
) -> ChainResult:
    """Stops starting new attempts once `budget_seconds` have passed, so a reading always
    finishes well before the 2-minute stale sweep would hand it to manual entry."""
    result = ChainResult(extraction=None)
    deadline = clock() + budget_seconds
    for provider in providers:
        for attempt in (1, 2):
            if clock() >= deadline:
                result.attempts.append(
                    {
                        "provider": provider.name,
                        "model": None,
                        "prompt_version": PROMPT_VERSION,
                        "started_at": datetime.now(UTC).isoformat(),
                        "ms": 0,
                        "outcome": "error",
                        "error_code": "deadline_exceeded",
                        "http_status": None,
                    }
                )
                return result
            started = datetime.now(UTC)
            t0 = time.monotonic()
            record: dict[str, Any] = {
                "provider": provider.name,
                "model": None,
                "prompt_version": PROMPT_VERSION,
                "started_at": started.isoformat(),
            }
            try:
                raw = provider.extract(images=images, text=text)
                extraction = BillExtraction.model_validate(raw)
            except ProviderError as exc:
                record.update(outcome="error", error_code=exc.kind, http_status=exc.status)
                _finish(record, provider, t0, result)
                if exc.kind in RETRYABLE and attempt == 1:
                    sleep(min(exc.retry_after or 1.0, MAX_RETRY_WAIT))
                    continue
                break
            except ValidationError:
                record.update(outcome="error", error_code="invalid_response", http_status=None)
                _finish(record, provider, t0, result)
                break
            except Exception as exc:  # a provider bug must not skip the remaining providers
                log.warning("provider %s raised %s", provider.name, type(exc).__name__)
                record.update(outcome="error", error_code="unexpected", http_status=None)
                _finish(record, provider, t0, result)
                break
            record.update(outcome="ok", error_code=None, http_status=None)
            _finish(record, provider, t0, result)
            result.extraction, result.raw = extraction, raw
            result.provider, result.model = provider.name, provider.last_model
            return result
    return result


def _finish(record: dict[str, Any], provider: Provider, t0: float, result: ChainResult) -> None:
    record["model"] = provider.last_model
    record["ms"] = round((time.monotonic() - t0) * 1000)
    result.attempts.append(record)
