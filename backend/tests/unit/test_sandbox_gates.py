"""Unit tests for sandbox DoS gates: concurrency, budget, dedup, circuit breaker.

Covers scenarios from:
- Feature: Sandbox DoS gates (bdd-specs.md §2)
- tasks 008a/b, 009a/b, 010a/b
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.core.sandbox_gates import (
    SandboxBudgetLimiter,
    SandboxCircuitBreaker,
    SandboxConcurrencyLimiter,
    SandboxDedupCache,
)

# ---- Concurrency --------------------------------------------------------


def test_concurrency_cap_rejects_beyond_max() -> None:
    gate = SandboxConcurrencyLimiter(max_concurrent=3)
    assert gate.try_acquire() is True
    assert gate.try_acquire() is True
    assert gate.try_acquire() is True
    assert gate.try_acquire() is False
    assert gate.in_flight == 3


def test_concurrency_released_after_completion() -> None:
    gate = SandboxConcurrencyLimiter(max_concurrent=2)
    gate.try_acquire()
    gate.try_acquire()
    assert gate.try_acquire() is False
    gate.release()
    assert gate.try_acquire() is True


def test_concurrency_guard_context_manager() -> None:
    gate = SandboxConcurrencyLimiter(max_concurrent=1)
    with gate.guard() as acquired:
        assert acquired is True
        with gate.guard() as nested:
            assert nested is False  # cap reached, nested rejected
    # After outer exits, slot is released.
    with gate.guard() as acquired:
        assert acquired is True


# ---- Per-agent budget ---------------------------------------------------


def test_budget_exhausted_after_max_calls() -> None:
    budget = SandboxBudgetLimiter(max_calls=3, window_seconds=60.0)
    agent = uuid4()
    assert budget.try_consume(agent, now=0.0) is True
    assert budget.try_consume(agent, now=1.0) is True
    assert budget.try_consume(agent, now=2.0) is True
    assert budget.try_consume(agent, now=3.0) is False


def test_budget_rolls_forward_after_window() -> None:
    budget = SandboxBudgetLimiter(max_calls=2, window_seconds=60.0)
    agent = uuid4()
    budget.try_consume(agent, now=0.0)
    budget.try_consume(agent, now=1.0)
    assert budget.try_consume(agent, now=10.0) is False
    # 61 seconds later the first slot has expired.
    assert budget.try_consume(agent, now=61.0) is True


def test_budget_retry_after_seconds_is_reported() -> None:
    budget = SandboxBudgetLimiter(max_calls=1, window_seconds=60.0)
    agent = uuid4()
    budget.try_consume(agent, now=0.0)
    remaining = budget.retry_after_seconds(agent, now=30.0)
    assert remaining == 30.0


# ---- Dedup cache --------------------------------------------------------


def test_dedup_cache_returns_cached_verdict_within_window() -> None:
    cache = SandboxDedupCache(window_minutes=10)
    now = datetime.now(tz=UTC)
    run_id = cache.put(
        "fix the bug",
        "KeyError: 'x'",
        sandbox_score=1.0,
        success=True,
        now=now,
    )
    hit = cache.get("fix the bug", "KeyError: 'x'", now=now + timedelta(minutes=3))
    assert hit is not None
    assert hit.run_id == run_id
    assert hit.success is True


def test_dedup_cache_expires_after_window() -> None:
    cache = SandboxDedupCache(window_minutes=10)
    now = datetime.now(tz=UTC)
    cache.put("fix", "sig", sandbox_score=1.0, success=True, now=now)
    expired = cache.get("fix", "sig", now=now + timedelta(minutes=11))
    assert expired is None


def test_dedup_normalization_collapses_whitespace() -> None:
    cache = SandboxDedupCache(window_minutes=10)
    now = datetime.now(tz=UTC)
    cache.put("fix   the\nbug", "sig", sandbox_score=1.0, success=True, now=now)
    hit = cache.get("fix the bug", "sig", now=now)
    assert hit is not None


# ---- Circuit breaker ----------------------------------------------------


def test_circuit_breaker_trips_on_container_error_rate() -> None:
    breaker = SandboxCircuitBreaker(
        error_rate=0.20, min_samples=10, window_minutes=5, cooldown_minutes=5
    )
    t0 = datetime.now(tz=UTC)
    # 79 successes + 21 container_errors = 21% error rate over 100 samples.
    for i in range(79):
        breaker.record("success", now=t0 + timedelta(seconds=i))
    for i in range(21):
        breaker.record("container_error", now=t0 + timedelta(seconds=79 + i))
    assert breaker.state == "open"
    assert breaker.should_allow(now=t0 + timedelta(seconds=101)) is False


def test_circuit_breaker_does_not_trip_on_sandbox_fail_verdicts() -> None:
    breaker = SandboxCircuitBreaker(
        error_rate=0.20, min_samples=10, window_minutes=5, cooldown_minutes=5
    )
    t0 = datetime.now(tz=UTC)
    for i in range(79):
        breaker.record("success", now=t0 + timedelta(seconds=i))
    for i in range(21):
        breaker.record("sandbox_fail", now=t0 + timedelta(seconds=79 + i))
    assert breaker.state == "closed"


def test_circuit_breaker_closes_after_cooldown_on_probe_success() -> None:
    breaker = SandboxCircuitBreaker(
        error_rate=0.20, min_samples=10, window_minutes=5, cooldown_minutes=5
    )
    t0 = datetime.now(tz=UTC)
    for _ in range(10):
        breaker.record("container_error", now=t0)
    assert breaker.state == "open"
    # After cooldown, probing allowed.
    t_probe = t0 + timedelta(minutes=5, seconds=1)
    assert breaker.should_allow(now=t_probe) is True
    assert breaker.state == "probing"
    breaker.record("success", now=t_probe)
    assert breaker.state == "closed"


def test_circuit_breaker_reopens_on_probe_failure() -> None:
    breaker = SandboxCircuitBreaker(
        error_rate=0.20, min_samples=10, window_minutes=5, cooldown_minutes=5
    )
    t0 = datetime.now(tz=UTC)
    for _ in range(10):
        breaker.record("container_error", now=t0)
    t_probe = t0 + timedelta(minutes=5, seconds=1)
    breaker.should_allow(now=t_probe)
    assert breaker.state == "probing"
    breaker.record("container_error", now=t_probe)
    assert breaker.state == "open"
