# Task 009b: GET /v1/dashboard/research/stream SSE endpoint — Green

**depends-on**: 009a

## Description

Implement the SSE stream endpoint at `/v1/dashboard/research/stream` inside the existing dashboard router. Per-connection 2-second poll-and-diff loop; `:heartbeat` comment lines every 25 s; 15-minute hard server-side timeout; per-IP / per-agent / per-worker concurrency caps via the `008b` limiter; in-process 10-second cache for `last_cycle_at`; structured logs on each `research_started` / `research_ended` event.

## Execution Context

**Task Number**: 009b of 20
**Phase**: Presentation — SSE Stream Green
**Prerequisites**: Task 009a (failing tests).

## BDD Scenario

(Same scenarios as 009a — this task makes the 13 tests PASS.)

## Files to Modify/Create

- Modify: `backend/presentation/api/routes/dashboard.py`
- Modify: `backend/core/config.py` (expose `POLL_INTERVAL_SECONDS`, `HEARTBEAT_INTERVAL_SECONDS`, `HARD_TIMEOUT_SECONDS`, `LAST_CYCLE_CACHE_TTL_SECONDS` so they can be tuned without redeploying every worker)

## Steps

### Step 1: Add module-level constants

In `backend/core/config.py`, add (with defaults from design `architecture.md §3`):

```python
POLL_INTERVAL_SECONDS: float = 2.0
HEARTBEAT_INTERVAL_SECONDS: float = 25.0
HARD_TIMEOUT_SECONDS: int = 15 * 60
LAST_CYCLE_CACHE_TTL_SECONDS: float = 10.0
```

### Step 2: Add the endpoint

In `backend/presentation/api/routes/dashboard.py`, append (signatures only):

```python
import asyncio
import json
import logging
from time import monotonic

from fastapi.responses import StreamingResponse

from backend.core.config import (
    HARD_TIMEOUT_SECONDS,
    HEARTBEAT_INTERVAL_SECONDS,
    LAST_CYCLE_CACHE_TTL_SECONDS,
    POLL_INTERVAL_SECONDS,
)
from backend.core.sse_concurrency import (
    TooManyConcurrentStreams,
    limiter as sse_limiter,
)

logger = logging.getLogger(__name__)


@router.get("/research/stream")
async def stream_live_research(
    request: Request,
    service: AgentbookService = Depends(get_service),
) -> StreamingResponse:
    """Public SSE stream of live research state.

    Per-connection 2 s poll diff. :heartbeat every 25 s. Hard-close at
    15 minutes (clients reconnect transparently). Concurrency capped by
    backend.core.sse_concurrency.limiter.
    """
    ...
```

### Step 3: Diff loop contract

Inside the endpoint body, the async generator must:

1. Identify the limiter key: `agent_id` (from `request.state.agent`) when authenticated, else `request.client.host`.
2. Acquire a slot via `sse_limiter.acquire(key, authenticated=...)` — on `TooManyConcurrentStreams`, return a `JSONResponse({"error": "rate_limit_exceeded"}, status_code=429)` BEFORE constructing the StreamingResponse.
3. Inside the generator (now holding the slot):
   - Compute initial snapshot via `service.get_live_research_snapshot()`.
   - Cache `last_cycle_at` with `(value, monotonic_ts)`; refresh if `monotonic() - ts > LAST_CYCLE_CACHE_TTL_SECONDS`.
   - Emit `event: snapshot\nid: 0\ndata: {…}\n\n`.
   - Track `last_active = {a["problem_id"]: a for a in snapshot["active"]}`.
   - Loop while `monotonic() - started_at < HARD_TIMEOUT_SECONDS`:
     - `await asyncio.sleep(POLL_INTERVAL_SECONDS)`.
     - Recompute snapshot (using cache for `last_cycle_at`).
     - Diff: emit `event: research_started` for each new pid; emit `event: research_ended` for each removed pid.
     - On every emit, log structured: `logger.info("sse_event", extra={"event": "research_started", "problem_id": pid, "now": …})`.
     - Every `HEARTBEAT_INTERVAL_SECONDS`, emit `:heartbeat <iso-now>\n\n`.
4. Wrap the generator in `StreamingResponse(generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"})`.

### Step 4: Helper for SSE frame formatting

Add a small private helper (no public surface):

```python
def _format_event(event: str, data: dict, *, event_id: int) -> str:
    """Serialise an SSE frame: `event: <e>\\nid: <id>\\ndata: <json>\\n\\n`."""
    ...
```

The function is module-private (underscore-prefixed) and is unit-tested via the integration tests in 009a, not directly.

### Step 5: Run tests to confirm Green
```bash
uv run pytest backend/tests/unit/test_dashboard_stream_route.py -x
```

All 13 tests must PASS.

### Step 6: Smoke test against running server
```bash
DEMO_MODE=1 uv run uvicorn backend.main:app --reload &
sleep 2
curl -sN -H "Accept: text/event-stream" http://localhost:8000/v1/dashboard/research/stream | head -c 2000
# Expected: a valid `event: snapshot` followed by JSON data
kill %1
```

### Step 7: Format and lint
```bash
uv run ruff format backend/presentation/api/routes/dashboard.py backend/core/config.py
uv run ruff check --fix backend/presentation/api/routes/dashboard.py backend/core/config.py
```

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_dashboard_stream_route.py -x
uv run ruff check backend/presentation/api/routes/dashboard.py backend/core/config.py
```

## Success Criteria

- 13/13 tests pass.
- The 4 timing constants live in `backend/core/config.py`, not hard-coded in the route file.
- `Last-Event-ID` is read but ignored — server starts each connection with a fresh `id: 0` snapshot.
- Heartbeat is a comment line (`:heartbeat …\n\n`), not an `event: heartbeat` data event.
- Hard-timeout closes the response cleanly via the generator's normal termination — no `asyncio.CancelledError` leakage.
- Structured logs on every diff event include `event` and `problem_id` keys.
- 10-second `last_cycle_at` cache verified by query counter assertion in the test suite.
- No new dependency.
- Existing dashboard endpoints still work.
