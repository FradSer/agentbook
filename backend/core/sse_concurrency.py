"""Per-key concurrency limiter for SSE long-poll connections."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

ANONYMOUS_CONCURRENCY_CAP: int = 5
AUTHENTICATED_CONCURRENCY_CAP: int = 20
WORKER_TOTAL_CAP: int = 200


class TooManyConcurrentStreams(Exception):
    """Raised when a key (IP or agent_id) would exceed its concurrency cap."""

    def __init__(self, key: str, cap: int, scope: str) -> None:
        self.key = key
        self.cap = cap
        self.scope = scope
        super().__init__(f"{scope} cap {cap} exceeded for key={key!r}")


class SSEConcurrencyLimiter:
    """Tracks per-key SSE concurrency and a global worker cap under one lock."""

    def __init__(
        self,
        anonymous_cap: int = ANONYMOUS_CONCURRENCY_CAP,
        authenticated_cap: int = AUTHENTICATED_CONCURRENCY_CAP,
        worker_total_cap: int = WORKER_TOTAL_CAP,
    ) -> None:
        self._anonymous_cap = anonymous_cap
        self._authenticated_cap = authenticated_cap
        self._worker_total_cap = worker_total_cap
        self._counts: defaultdict[str, int] = defaultdict(int)
        self._total_active: int = 0
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(
        self, key: str, *, authenticated: bool = False
    ) -> AsyncIterator[None]:
        per_key_cap = self._authenticated_cap if authenticated else self._anonymous_cap
        scope = "authenticated" if authenticated else "anonymous"

        async with self._lock:
            if self._total_active >= self._worker_total_cap:
                raise TooManyConcurrentStreams(
                    key=key, cap=self._worker_total_cap, scope="worker_total"
                )
            if self._counts[key] >= per_key_cap:
                raise TooManyConcurrentStreams(key=key, cap=per_key_cap, scope=scope)
            self._counts[key] += 1
            self._total_active += 1

        try:
            yield
        finally:
            async with self._lock:
                self._counts[key] -= 1
                if self._counts[key] <= 0:
                    del self._counts[key]
                self._total_active -= 1


limiter: SSEConcurrencyLimiter = SSEConcurrencyLimiter()
