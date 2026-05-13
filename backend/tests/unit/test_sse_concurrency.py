"""Unit tests for the SSE per-key concurrency limiter."""

from __future__ import annotations

import asyncio

import pytest

from backend.core.sse_concurrency import (
    SSEConcurrencyLimiter,
    TooManyConcurrentStreams,
)


@pytest.mark.asyncio
async def test_acquire_under_cap_returns_token() -> None:
    """Acquire #1..#5 for the same IP each enter the context manager cleanly."""
    limiter = SSEConcurrencyLimiter(anonymous_cap=5)
    holders = []
    try:
        for _ in range(5):
            cm = limiter.acquire("10.0.0.1", authenticated=False)
            await cm.__aenter__()
            holders.append(cm)
    finally:
        for cm in holders:
            await cm.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_acquire_at_cap_raises_too_many_concurrent_streams() -> None:
    """The 6th acquire for the same IP raises TooManyConcurrentStreams."""
    limiter = SSEConcurrencyLimiter(anonymous_cap=5)
    holders = []
    for _ in range(5):
        cm = limiter.acquire("10.0.0.2", authenticated=False)
        await cm.__aenter__()
        holders.append(cm)
    try:
        with pytest.raises(TooManyConcurrentStreams):
            async with limiter.acquire("10.0.0.2", authenticated=False):
                pass
    finally:
        for cm in holders:
            await cm.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_release_decrements_counter() -> None:
    """Releasing one of 5 connections frees a slot for a new acquire."""
    limiter = SSEConcurrencyLimiter(anonymous_cap=5)
    holders = []
    for _ in range(5):
        cm = limiter.acquire("10.0.0.3", authenticated=False)
        await cm.__aenter__()
        holders.append(cm)

    # Release one slot.
    await holders.pop().__aexit__(None, None, None)

    # A new acquire should now succeed.
    async with limiter.acquire("10.0.0.3", authenticated=False):
        pass

    for cm in holders:
        await cm.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_authenticated_cap_is_20() -> None:
    """Acquire 21 with the same agent_id raises; 20 succeed."""
    limiter = SSEConcurrencyLimiter(authenticated_cap=20)
    holders = []
    try:
        for _ in range(20):
            cm = limiter.acquire("agent-x", authenticated=True)
            await cm.__aenter__()
            holders.append(cm)
        with pytest.raises(TooManyConcurrentStreams):
            async with limiter.acquire("agent-x", authenticated=True):
                pass
    finally:
        for cm in holders:
            await cm.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_total_per_worker_cap_is_200() -> None:
    """The 201st distinct IP acquire raises TooManyConcurrentStreams."""
    limiter = SSEConcurrencyLimiter(
        anonymous_cap=5, authenticated_cap=20, worker_total_cap=200
    )
    holders = []
    try:
        for i in range(200):
            cm = limiter.acquire(f"10.1.0.{i}", authenticated=False)
            await cm.__aenter__()
            holders.append(cm)
        with pytest.raises(TooManyConcurrentStreams):
            async with limiter.acquire("10.1.99.99", authenticated=False):
                pass
    finally:
        for cm in holders:
            await cm.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_concurrent_acquires_use_lock() -> None:
    """asyncio.gather of 10 acquires at cap=5 yields exactly 5 successes and 5 raises."""
    limiter = SSEConcurrencyLimiter(anonymous_cap=5)
    succeeded: list[bool] = []
    failed: list[bool] = []
    barrier = asyncio.Event()

    async def worker() -> None:
        try:
            async with limiter.acquire("10.2.0.1", authenticated=False):
                succeeded.append(True)
                # Hold the slot until everyone has tried to acquire.
                await barrier.wait()
        except TooManyConcurrentStreams:
            failed.append(True)

    tasks = [asyncio.create_task(worker()) for _ in range(10)]
    # Give every task a turn to attempt acquire.
    for _ in range(20):
        await asyncio.sleep(0)
    barrier.set()
    await asyncio.gather(*tasks)

    assert len(succeeded) == 5
    assert len(failed) == 5


@pytest.mark.asyncio
async def test_release_via_finally_runs_even_on_exception() -> None:
    """Context manager decrements the counter even when the body raises."""
    limiter = SSEConcurrencyLimiter(anonymous_cap=1)

    with pytest.raises(RuntimeError):
        async with limiter.acquire("10.3.0.1", authenticated=False):
            raise RuntimeError("boom")

    # The slot must be released — a second acquire should succeed.
    async with limiter.acquire("10.3.0.1", authenticated=False):
        pass
