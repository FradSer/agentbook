# Task 008a: core/sse_concurrency.py per-IP semaphore — Red

**depends-on**: 002

## Description

Add failing unit tests for the new SSE concurrency-limiter primitive at `backend/core/sse_concurrency.py`. The primitive is a small `defaultdict[str, int]` guarded by an `asyncio.Lock` that tracks per-key (IP or agent_id) concurrent SSE connections, enforcing 5/IP (anonymous), 20/agent (authenticated), and 200/worker total caps. Tests must FAIL until task 008b lands.

This module is independent of the 005/007 backend stack; it can be developed in parallel with the service / REST work.

## Execution Context

**Task Number**: 008a of 20
**Phase**: Presentation — SSE Limiter Red
**Prerequisites**: Task 002 (Protocol additions — semaphore is independent but lives in the same import graph).

## BDD Scenario

```gherkin
Scenario: Concurrent SSE connections per anonymous IP are capped at 5
  Given the configured per-IP cap is 5 concurrent SSE connections
  And the same remote IP already holds 5 open SSE connections
  When the same IP opens a 6th SSE connection
  Then the server responds with status 429
  And the response body contains error "rate_limit_exceeded"
  And the existing 5 connections from that IP are not affected
```

**Spec Source**: `../2026-05-01-live-research-banner-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_sse_concurrency.py`

## Steps

### Step 1: Write failing tests (Red)

Required test contracts:

```python
async def test_acquire_under_cap_returns_token():
    """Acquire #1..#5 for the same IP each return a context manager."""
    ...

async def test_acquire_at_cap_raises_too_many_concurrent_streams():
    """Acquire #6 for the same IP raises TooManyConcurrentStreams."""
    ...

async def test_release_decrements_counter():
    """After releasing one of 5 connections, a new acquire for that IP succeeds."""
    ...

async def test_authenticated_cap_is_20():
    """Acquire 21 with the same agent_id raises; 20 succeed."""
    ...

async def test_total_per_worker_cap_is_200():
    """Across 200 distinct IPs (1 each), the 201st acquire raises TooManyConcurrentStreams."""
    ...

async def test_concurrent_acquires_use_lock():
    """asyncio.gather of 10 acquires for the same IP at cap=5 → exactly 5 succeed, 5 raise."""
    ...

async def test_release_via_finally_runs_even_on_exception():
    """Test that the context manager decrements the counter when the body raises."""
    ...
```

Use `pytest-asyncio` (already in the test deps). Tests should mock no external state — the module is pure in-process.

### Step 2: Confirm Red
```bash
uv run pytest backend/tests/unit/test_sse_concurrency.py -x
```

All 7 tests must FAIL with `ModuleNotFoundError: No module named 'backend.core.sse_concurrency'`.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_sse_concurrency.py -x
# Expected: 7 FAILED tests, ModuleNotFoundError
```

## Success Criteria

- 7 tests added, all FAIL for the intended reason.
- Tests use `pytest-asyncio` markers consistent with the rest of the repo.
- Tests cover both anonymous (IP-keyed) and authenticated (agent-id-keyed) caps.
- Lock contention test asserts deterministic outcome under `asyncio.gather`.
- No production code created in this task.
