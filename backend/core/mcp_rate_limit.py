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

import time
from collections import OrderedDict, deque
from threading import Lock

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
        self._max = max_calls
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
            if len(bucket) >= self._max:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        """Clear all buckets. Intended for test hygiene."""
        with self._lock:
            self._buckets.clear()


def mcp_rate_key(agent: Agent | None, remote_addr: str | None) -> str:
    """Build a rate-limit bucket key.

    Authenticated callers key by agent id so their quota is independent of
    any anonymous traffic from the same IP. Mirrors `core.rate_limit._rate_key`.
    """
    if agent is not None:
        return f"agent:{agent.agent_id}"
    return f"ip:{remote_addr or 'unknown'}"


# Mirrors the REST `/v1/search` contract: 30 per minute per agent/IP.
mcp_search_limiter = MCPRateLimiter(max_calls=30, window_seconds=60)
