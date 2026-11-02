"""In-memory sliding-window limiter.

One instance per app (stored on app.state), so it is fine for the single Render
instance the architecture assumes; a shared store (Redis) is a documented next step.
"""

import time
from collections import deque
from collections.abc import Callable
from threading import Lock

from starlette.requests import Request

from app.core.config import get_settings


def client_ip(request: Request) -> str:
    """The caller's IP. Behind Vercel → Render the socket peer is a proxy, so the first
    X-Forwarded-For hop is used — only when TRUST_PROXY_HEADERS is on, because the header
    is client-controlled when no trusted proxy sits in front."""
    if get_settings().trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


class SlidingWindowLimiter:
    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ):
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _prune(self, key: str, now: float) -> int:
        """Drop expired hits; forget the key entirely once empty. Returns live hit count."""
        hits = self._hits.get(key)
        if hits is None:
            return 0
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if not hits:
            del self._hits[key]
            return 0
        return len(hits)

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            return self._prune(key, self._clock()) >= self.limit

    def record(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            self._prune(key, now)
            self._hits.setdefault(key, deque()).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def size(self) -> int:
        with self._lock:
            return len(self._hits)
