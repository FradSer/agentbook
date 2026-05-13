"""In-process rate limiter for MCP public tools.

REST `/v1/search` is throttled via slowapi, but MCP tool calls bypass
FastAPI routing entirely — they dispatch through `dispatch_tool()` on raw
ASGI scope. This module provides a sliding-window limiter keyed by the
authenticated agent (when present) or the remote address, matching the
REST contract of 30 requests per minute per caller.

In-memory and process-local. Horizontal scaling will want a shared store,
same caveat as the slowapi default.
"""

from __future__ import annotations

import math
import time
from collections import OrderedDict, deque
from threading import Lock

from backend.core._rate_keys import format_rate_key
from backend.domain.models import Agent


class MCPRateLimiter:
    """Fixed-capacity sliding window rate limiter with LRU bucket eviction.

    `max_keys` caps the number of tracked buckets so a public endpoint
    seeing high IP churn cannot grow `_buckets` without bound. Eviction
    order is insertion/recency via `OrderedDict.move_to_end`.
    """

    def __init__(
        self,
        *,
        max_calls: int,
        window_seconds: float,
        max_keys: int = 10_000,
    ) -> None:
        self.max_calls = max_calls
        self._window = window_seconds
        self._max_keys = max_keys
        self._buckets: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()
        self.enabled = True

    def hit(self, key: str) -> bool:
        """Record a hit for `key`. Returns True when allowed, False when throttled."""
        if not self.enabled:
            return True
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= self._max_keys:
                    self._buckets.popitem(last=False)
                bucket = deque()
                self._buckets[key] = bucket
            else:
                self._buckets.move_to_end(key)

            cutoff = now - self._window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_calls:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        """Clear all buckets. Intended for test hygiene."""
        with self._lock:
            self._buckets.clear()

    def retry_after(self, key: str) -> int:
        """Seconds until ``key`` can hit again.

        Returns 0 when the bucket has room (caller should not have asked).
        Otherwise returns the seconds until the oldest hit ages out of the
        sliding window, floored to 1 — advising 0 to a throttled caller
        just re-trips the bucket and is the entire reason this method
        exists.
        """
        if not self.enabled:
            return 0
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or len(bucket) < self.max_calls:
                return 0
            oldest = bucket[0]
            remaining = self._window - (time.monotonic() - oldest)
            if remaining <= 0:
                return 0
            # Floor of 1s — advising 0 to a throttled caller just re-trips.
            return max(1, math.ceil(remaining))


# MCP key formatter is intentionally identical to REST's. Both surfaces
# must produce the same key for a given caller (the limiters keep
# separate state — see ``backend/core/rate_limit.py``).
mcp_rate_key = format_rate_key


# Mirrors the REST `/v1/search` contract: 30 per minute per IP for anon callers.
mcp_search_limiter = MCPRateLimiter(max_calls=30, window_seconds=60)
# Authenticated agents get a higher quota to support batch debugging.
mcp_search_limiter_auth = MCPRateLimiter(max_calls=300, window_seconds=60)

# `verify` is synchronous and blocks the MCP request for the duration
# of the sandbox run (Docker pull + python execution, easily multi-second).
# Without an explicit per-agent throttle independent of the sandbox
# budget, a single agent can monopolise all 8 sandbox slots and starve
# every other caller's improve / verify path. 5/min is the smallest
# limit that still lets a real debug loop verify a candidate, retry on
# transient flake, and re-verify after a fix in the same minute.
mcp_verify_limiter = MCPRateLimiter(max_calls=5, window_seconds=60)


def pick_mcp_search_limiter(agent: Agent | None) -> MCPRateLimiter:
    """Return the limiter that matches the caller's authentication tier."""
    return mcp_search_limiter_auth if agent is not None else mcp_search_limiter
