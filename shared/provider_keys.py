"""Round-robin key selection shared by the API and the ReviewerAgent.

A provider credential setting (e.g. ``GEMINI_API_KEY``) may hold a single key
or a comma-separated list. ``parse_keys`` normalises that into a clean list and
``RoundRobin`` hands out the next key on each call, spreading load across keys
so one throttled/dead key does not sink every request. Selection-level
resilience only: a 401/429 on the chosen key is not retried mid-request — the
provider fallback chain handles a wholly-unconfigured provider.

``RoundRobin`` is thread-safe because the embedding path runs synchronously on
request threads while the agent path runs under asyncio; a single rotator may
be shared across both.
"""

from __future__ import annotations

import threading


def parse_keys(raw: str | None) -> list[str]:
    """Split a single key or comma-separated list into clean entries."""
    if not raw:
        return []
    return [key.strip() for key in raw.split(",") if key.strip()]


class RoundRobin:
    """Thread-safe rotating selector over a fixed list of keys."""

    def __init__(self, keys: list[str]) -> None:
        self._keys = list(keys)
        self._index = 0
        self._lock = threading.Lock()

    def __bool__(self) -> bool:
        return bool(self._keys)

    def next(self) -> str:
        if not self._keys:
            raise ValueError("RoundRobin has no keys")
        with self._lock:
            key = self._keys[self._index]
            self._index = (self._index + 1) % len(self._keys)
        return key
