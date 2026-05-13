# Task 008b: core/sse_concurrency.py per-IP semaphore — Green

**depends-on**: 008a

## Description

Implement `backend/core/sse_concurrency.py` with the per-key concurrency tracker plus an async context manager. Public surface: `SSEConcurrencyLimiter` class with `acquire(key, cap)` returning an async context manager and a module-level singleton ready to plug into the SSE handler.

## Execution Context

**Task Number**: 008b of 20
**Phase**: Presentation — SSE Limiter Green
**Prerequisites**: Task 008a (failing tests).

## BDD Scenario

(Same as 008a — this task makes the 7 tests PASS.)

## Files to Modify/Create

- Create: `backend/core/sse_concurrency.py`

## Steps

### Step 1: Implement the module

Public contracts (signatures only — body is implementation):

```python
"""Per-key concurrency limiter for SSE long-poll connections.

slowapi qps-based throttling is meaningless for long-lived streams; this
module tracks live connections instead, enforcing per-IP / per-agent /
per-worker caps with O(1) acquire and release.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


ANONYMOUS_CONCURRENCY_CAP: int = 5
AUTHENTICATED_CONCURRENCY_CAP: int = 20
WORKER_TOTAL_CAP: int = 200


class TooManyConcurrentStreams(Exception):
    """Raised when a key (IP or agent_id) would exceed its concurrency cap."""

    def __init__(self, key: str, cap: int, scope: str) -> None: ...


class SSEConcurrencyLimiter:
    """Tracks concurrent SSE connections by key.

    Thread-safety: protected by a single asyncio.Lock; the critical section
    is two dict reads and one dict write, so contention is negligible.
    """

    def __init__(
        self,
        anonymous_cap: int = ANONYMOUS_CONCURRENCY_CAP,
        authenticated_cap: int = AUTHENTICATED_CONCURRENCY_CAP,
        worker_total_cap: int = WORKER_TOTAL_CAP,
    ) -> None: ...

    @asynccontextmanager
    async def acquire(
        self, key: str, *, authenticated: bool = False
    ) -> AsyncIterator[None]: ...


limiter: SSEConcurrencyLimiter = SSEConcurrencyLimiter()
```

Implementation rules:

- The acquire/release counters are kept in a `defaultdict[str, int]` plus an integer `_total_active`.
- `acquire` increments the per-key counter and `_total_active` under the lock; if either would exceed its cap it raises `TooManyConcurrentStreams` BEFORE incrementing.
- The `asynccontextmanager` finally-block decrements both counters under the same lock.
- Exception in the wrapped body must still trigger the decrement (this is what the `try/finally` shape gives you for free).
- Module-level `limiter` is the singleton the SSE handler imports.

### Step 2: Run tests to confirm Green
```bash
uv run pytest backend/tests/unit/test_sse_concurrency.py -x
```

All 7 tests must PASS.

### Step 3: Format and lint
```bash
uv run ruff format backend/core/sse_concurrency.py
uv run ruff check --fix backend/core/sse_concurrency.py
```

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_sse_concurrency.py -x
uv run python -c "from backend.core.sse_concurrency import limiter, SSEConcurrencyLimiter, TooManyConcurrentStreams"
uv run ruff check backend/core/sse_concurrency.py
```

## Success Criteria

- 7/7 tests in `test_sse_concurrency.py` pass.
- Module exports `limiter`, `SSEConcurrencyLimiter`, `TooManyConcurrentStreams`, and the three cap constants.
- All public surface uses async context-manager idiom.
- O(1) acquire/release under the lock — no per-key dict iteration.
- No new dependency added.
