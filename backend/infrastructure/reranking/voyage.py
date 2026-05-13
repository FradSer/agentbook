"""Voyage AI cross-encoder reranker with in-process rate-limit guard.

``rerank-2.5-lite`` is the latency-optimised variant — ~80-120 ms p50 for
top-30 vs ~200-350 ms for full ``rerank-2.5``. Voyage's rerank endpoint caps
at **100 RPM** per account (vs the authenticated search tier of 300 RPM),
so an in-process token bucket guards the call site: when exhausted, the
reranker silently degrades to identity ordering rather than surface 429s
to clients. Phase 1 scoring already ensures the search remains correct
without rerank.

Lazy import: ``voyageai`` is optional; when missing, ``resolve_rerank_fn``
returns ``noop_rerank`` and the chain stays graceful.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque

from backend.core.config import settings
from backend.domain.services import RerankFn
from backend.infrastructure.reranking.noop import noop_rerank

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised only when voyageai is installed
    import voyageai
except Exception:  # noqa: BLE001 - any import failure disables the provider
    voyageai = None  # type: ignore[assignment]


class _RateLimitBucket:
    """Sliding-window counter; thread-safe, monotonic, no external deps.

    100 successful calls within any 60-second window. ``acquire`` peels off
    expired timestamps, then either records the new call (return True) or
    refuses (return False). Refusals are visible to the caller so they can
    degrade behaviour rather than block."""

    def __init__(self, capacity: int = 100, window_seconds: float = 60.0) -> None:
        self._capacity = capacity
        self._window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        with self._lock:
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            if len(self._timestamps) >= self._capacity:
                return False
            self._timestamps.append(now)
            return True

    def in_flight(self) -> int:
        with self._lock:
            return len(self._timestamps)


class VoyageReranker:
    """Callable reranker conforming to ``RerankFn``.

    Stamps a counter (``self.skipped_calls``) for every fall-through to NoOp
    so the ``/v1/health-metrics`` endpoint can surface rerank-skip pressure
    in production. The instance is meant to be a singleton owned by the
    composition root."""

    def __init__(
        self,
        api_key: str,
        model: str = "rerank-2.5-lite",
        rate_limit_rpm: int = 100,
    ) -> None:
        if voyageai is None:
            raise RuntimeError(
                "voyageai package is not installed. Run `uv add voyageai` "
                "before constructing VoyageReranker."
            )
        self._client = voyageai.Client(api_key=api_key)
        self._model = model
        self._bucket = _RateLimitBucket(capacity=rate_limit_rpm, window_seconds=60.0)
        self.skipped_calls = 0

    def __call__(self, query: str, candidates: list[str], top_k: int) -> list[int]:
        if not candidates:
            return []
        if not self._bucket.acquire():
            self.skipped_calls += 1
            logger.warning(
                "voyage-rerank-rate-limit-deferred in_flight=%d skipped=%d",
                self._bucket.in_flight(),
                self.skipped_calls,
            )
            return noop_rerank(query, candidates, top_k)

        try:
            response = self._client.rerank(
                query=query,
                documents=candidates,
                model=self._model,
                top_k=min(top_k, len(candidates)),
            )
        except Exception as exc:  # noqa: BLE001 - any failure → NoOp degrade
            self.skipped_calls += 1
            logger.warning(
                "voyage-rerank-error error=%s skipped=%d", exc, self.skipped_calls
            )
            return noop_rerank(query, candidates, top_k)

        # response.results is sorted by relevance descending; each entry has
        # ``index`` (position in the input ``documents`` list) plus
        # ``relevance_score``. Translate into the index-list contract.
        return [int(item.index) for item in response.results]


def resolve_rerank_fn() -> RerankFn:
    """Build a ``VoyageReranker`` if ``VOYAGE_API_KEY`` is set; else NoOp.

    Returning ``noop_rerank`` rather than ``None`` keeps the ``RerankFn``
    type total in callers — they always receive a callable and never need
    to None-check before invoking."""
    if voyageai is None:
        return noop_rerank
    api_key = settings.voyage_api_key
    if not api_key or not settings.rerank_enabled:
        return noop_rerank
    return VoyageReranker(api_key=api_key, model=settings.voyage_rerank_model)
