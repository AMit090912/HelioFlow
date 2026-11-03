"""Groq and Gemini clients over plain httpx (§6.2). Keys travel only in headers, never in URLs.

Each provider returns the parsed JSON dict; schema validation happens in the chain, so every
provider is judged by the same contract. Failures raise ProviderError with a small, loggable kind.
"""

import base64
import json
import re
from typing import Any, Literal, Protocol

import httpx

from app.services.ai.prompt import (
    MAX_TEXT_CHARS,
    SYSTEM_PROMPT,
    USER_IMAGE_PROMPT,
    USER_TEXT_PROMPT,
)

ErrorKind = Literal[
    "rate_limited", "server", "timeout", "network", "auth", "bad_request", "invalid_response"
]
RETRYABLE: frozenset[str] = frozenset({"rate_limited", "server", "timeout", "network"})
# Groq sits behind Cloudflare, which rejects default library user agents.
USER_AGENT = "HelioFlow/0.1 (+bill-reading)"
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


class ProviderError(Exception):
    def __init__(
        self, kind: ErrorKind, status: int | None = None, retry_after: float | None = None
    ):
        super().__init__(kind)
        self.kind = kind
        self.status = status
        self.retry_after = retry_after


class Provider(Protocol):
    name: str
    last_model: str | None

    def extract(self, *, images: list[bytes] | None, text: str | None) -> dict[str, Any]: ...


def parse_json_reply(content: str | None) -> dict[str, Any]:
    """Tolerate reasoning blocks and code fences; require one JSON object."""
    if not content:
        raise ProviderError("invalid_response")
    cleaned = _THINK.sub("", content)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ProviderError("invalid_response")
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ProviderError("invalid_response") from exc
    if not isinstance(data, dict):
        raise ProviderError("invalid_response")
    return data


def _post(client: httpx.Client, url: str, headers: dict[str, str], body: dict) -> dict[str, Any]:
    try:
        response = client.post(url, headers={**headers, "User-Agent": USER_AGENT}, json=body)
    except httpx.TimeoutException as exc:
        raise ProviderError("timeout") from exc
    except httpx.TransportError as exc:
        raise ProviderError("network") from exc
    status = response.status_code
    if status == 429:
        try:
            retry_after = float(response.headers.get("retry-after", ""))
        except ValueError:
            retry_after = None
        raise ProviderError("rate_limited", status, retry_after)
    if status >= 500:
        raise ProviderError("server", status)
    if status in (401, 403):
        raise ProviderError("auth", status)
    if status >= 400:
        raise ProviderError("bad_request", status)
    try:
        return response.json()
    except ValueError as exc:
        raise ProviderError("invalid_response", status) from exc


def _timeouts(read_seconds: float) -> httpx.Timeout:
    """Short connect/write/pool limits; the model's thinking time is the read timeout."""
    return httpx.Timeout(read_seconds, connect=5.0, write=10.0, pool=5.0)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


class GroqProvider:
    name = "groq"
    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(
        self,
        api_key: str,
        vision_model: str,
        text_model: str,
        *,
        timeout: float,
        transport: httpx.BaseTransport | None = None,
    ):
        self._key, self._vision, self._text = api_key, vision_model, text_model
        self._client = httpx.Client(timeout=_timeouts(timeout), transport=transport)
        self.last_model: str | None = None

    def extract(self, *, images: list[bytes] | None, text: str | None) -> dict[str, Any]:
        if images:
            self.last_model = self._vision
            content: Any = [{"type": "text", "text": USER_IMAGE_PROMPT}] + [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(i)}"}}
                for i in images
            ]
        else:
            self.last_model = self._text
            content = USER_TEXT_PROMPT + (text or "")[:MAX_TEXT_CHARS]  # text models want a string
        body = {
            "model": self.last_model,
            "temperature": 0,
            "max_completion_tokens": 1500,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
        }
        reply = _post(self._client, self.URL, {"Authorization": f"Bearer {self._key}"}, body)
        try:
            message = reply["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("invalid_response") from exc
        return parse_json_reply(message)


class GeminiProvider:
    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout: float,
        transport: httpx.BaseTransport | None = None,
    ):
        self._key, self._model = api_key, model
        self._client = httpx.Client(timeout=_timeouts(timeout), transport=transport)
        self.last_model: str | None = None

    def extract(self, *, images: list[bytes] | None, text: str | None) -> dict[str, Any]:
        self.last_model = self._model
        prompt = USER_IMAGE_PROMPT if images else USER_TEXT_PROMPT + (text or "")[:MAX_TEXT_CHARS]
        parts: list[dict[str, Any]] = [{"text": prompt}]
        parts += [
            {"inline_data": {"mime_type": "image/jpeg", "data": _b64(i)}} for i in images or []
        ]
        body = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                # Reading a bill needs no long reasoning; Gemini 3 models think by default,
                # which made reads take 40–90 s. Older models don't accept this setting.
                **(
                    {"thinkingConfig": {"thinkingLevel": "low"}}
                    if self._model.startswith("gemini-3")
                    else {}
                ),
            },
        }
        reply = _post(
            self._client, self.URL.format(model=self._model), {"x-goog-api-key": self._key}, body
        )
        try:
            message = reply["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("invalid_response") from exc
        return parse_json_reply(message)
