"""Sandbox DoS gates: concurrency, per-agent budget, dedup, circuit breaker.

These run BEFORE the sandbox provider is invoked. Each gate raises or
returns a sentinel that the service layer translates into a safe
fallback path (typically ``sandbox_score=None`` so evaluate_improvement
falls back to the legacy Bayesian tree).
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class DedupHit:
    run_id: UUID
    sandbox_score: float
    success: bool
    created_at: datetime


class SandboxConcurrencyLimiter:
    """Global semaphore bounding simultaneous sandbox invocations."""

    def __init__(self, max_concurrent: int = 8) -> None:
        self.max_concurrent = max_concurrent
        self._sem = threading.BoundedSemaphore(max_concurrent)
        self._held = 0
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        got = self._sem.acquire(blocking=False)
        if got:
            with self._lock:
                self._held += 1
        return got

    def release(self) -> None:
        with self._lock:
            if self._held == 0:
                return
            self._held -= 1
        self._sem.release()

    @property
    def in_flight(self) -> int:
        return self._held

    @contextmanager
    def guard(self) -> Iterator[bool]:
        acquired = self.try_acquire()
        try:
            yield acquired
        finally:
            if acquired:
                self.release()


class SandboxBudgetLimiter:
    """Per-agent sliding-window budget (default 20 runs/hour)."""

    def __init__(self, *, max_calls: int = 20, window_seconds: float = 3600.0) -> None:
        self.max_calls = max_calls
        self._window = window_seconds
        self._buckets: dict[UUID, deque[float]] = {}
        self._lock = threading.Lock()

    def try_consume(self, agent_id: UUID, *, now: float | None = None) -> bool:
        t = time.monotonic() if now is None else now
        cutoff = t - self._window
        with self._lock:
            bucket = self._buckets.setdefault(agent_id, deque())
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_calls:
                return False
            bucket.append(t)
            return True

    def retry_after_seconds(self, agent_id: UUID, *, now: float | None = None) -> float:
        t = time.monotonic() if now is None else now
        with self._lock:
            bucket = self._buckets.get(agent_id)
            if not bucket:
                return 0.0
            oldest = bucket[0]
            return max(0.0, self._window - (t - oldest))

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


def _normalize_content(text: str) -> str:
    """Collapse interior whitespace; strip outer; lowercase-preserving."""
    return " ".join(text.split())


def _dedup_key(content: str, error_signature: str | None) -> str:
    raw = _normalize_content(content) + "|" + (error_signature or "")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SandboxDedupCache:
    """In-memory TTL cache on (normalized_content, error_signature)."""

    def __init__(self, *, window_minutes: int = 10, max_entries: int = 10_000) -> None:
        self._ttl = timedelta(minutes=window_minutes)
        self._max_entries = max_entries
        self._entries: dict[str, DedupHit] = {}
        self._lock = threading.Lock()

    def get(
        self,
        content: str,
        error_signature: str | None,
        *,
        now: datetime | None = None,
    ) -> DedupHit | None:
        t = now or datetime.now(tz=UTC)
        key = _dedup_key(content, error_signature)
        with self._lock:
            hit = self._entries.get(key)
            if hit is None:
                return None
            if (t - hit.created_at) > self._ttl:
                del self._entries[key]
                return None
            return hit

    def put(
        self,
        content: str,
        error_signature: str | None,
        *,
        sandbox_score: float,
        success: bool,
        now: datetime | None = None,
    ) -> UUID:
        t = now or datetime.now(tz=UTC)
        key = _dedup_key(content, error_signature)
        run_id = uuid4()
        hit = DedupHit(
            run_id=run_id, sandbox_score=sandbox_score, success=success, created_at=t
        )
        with self._lock:
            if len(self._entries) >= self._max_entries:
                # Evict arbitrary oldest entry by creation time.
                oldest_key = min(
                    self._entries, key=lambda k: self._entries[k].created_at
                )
                del self._entries[oldest_key]
            self._entries[key] = hit
        return run_id


_BREAKER_OUTCOME = Literal["success", "sandbox_fail", "container_error"]


class SandboxCircuitBreaker:
    """Trip on ``error_rate >= threshold`` over a sliding window.

    Distinguishes container errors (which trip the breaker) from
    ``sandbox_fail`` verdicts (which do not). After ``cooldown_minutes``
    the breaker enters ``probing`` state; the first call then runs. If
    the probe errors the breaker reopens for another cooldown window.
    """

    def __init__(
        self,
        *,
        error_rate: float = 0.20,
        min_samples: int = 10,
        window_minutes: int = 5,
        cooldown_minutes: int = 5,
    ) -> None:
        self._error_rate = error_rate
        self._min_samples = min_samples
        self._window = timedelta(minutes=window_minutes)
        self._cooldown = timedelta(minutes=cooldown_minutes)
        self._events: deque[tuple[datetime, str]] = deque()
        self._state: Literal["closed", "open", "probing"] = "closed"
        self._opened_at: datetime | None = None
        self._lock = threading.Lock()

    def should_allow(self, *, now: datetime | None = None) -> bool:
        t = now or datetime.now(tz=UTC)
        with self._lock:
            self._evict(t)
            if self._state == "open":
                if self._opened_at and (t - self._opened_at) >= self._cooldown:
                    self._state = "probing"
                    return True
                return False
            return True  # closed or probing

    def record(self, outcome: str, *, now: datetime | None = None) -> None:
        t = now or datetime.now(tz=UTC)
        with self._lock:
            self._events.append((t, outcome))
            self._evict(t)
            if self._state == "probing":
                if outcome == "container_error":
                    self._state = "open"
                    self._opened_at = t
                else:
                    self._state = "closed"
                    self._opened_at = None
                return
            total = len(self._events)
            if total < self._min_samples:
                return
            errors = sum(1 for _, o in self._events if o == "container_error")
            if errors / total >= self._error_rate:
                self._state = "open"
                self._opened_at = t

    def _evict(self, t: datetime) -> None:
        cutoff = t - self._window
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

    @property
    def state(self) -> str:
        return self._state

    @property
    def opened_at(self) -> datetime | None:
        return self._opened_at

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._state = "closed"
            self._opened_at = None
