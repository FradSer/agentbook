# Task 007b: GET /v1/dashboard/research/live REST endpoint — Green

**depends-on**: 007a

## Description

Implement the REST snapshot endpoint at `/v1/dashboard/research/live` inside the existing dashboard router. Wire `dynamic_search_limit`, `Cache-Control: no-store`, and confirm CORS works via the existing middleware (no per-route CORS overrides).

## Execution Context

**Task Number**: 007b of 20
**Phase**: Presentation — REST Green
**Prerequisites**: Task 007a (failing tests).

## BDD Scenario

(Same as 007a — this task makes them PASS.)

## Files to Modify/Create

- Modify: `backend/presentation/api/routes/dashboard.py`

## Steps

### Step 1: Add the endpoint

In `backend/presentation/api/routes/dashboard.py`, append (signatures only):

```python
from backend.core.rate_limit import dynamic_search_limit, limiter
from backend.presentation.api.schemas import LiveResearchSnapshotResponse


@router.get("/research/live", response_model=LiveResearchSnapshotResponse)
@limiter.limit(dynamic_search_limit)
def get_live_research(
    request: Request,
    service: AgentbookService = Depends(get_service),
) -> dict:
    """Public read of the live research snapshot.

    Anonymous: 30/minute by IP. Authenticated: 300/minute by agent.
    Cache-Control: no-store (data is real-time by definition).
    """
    ...
```

The handler is a dict-passthrough — call `service.get_live_research_snapshot()` and return the dict. FastAPI validates against `LiveResearchSnapshotResponse` automatically.

### Step 2: Add Cache-Control header

Use FastAPI's `Response` parameter or wrap the return in `JSONResponse(headers={"Cache-Control": "no-store"})`. Choose the dependency-injected `Response` form to avoid double serialisation.

### Step 3: Confirm route is registered
The endpoint lives in the existing `router` declared at the top of the file (`prefix="/v1/dashboard"`). `backend/presentation/api/router.py` already includes this router; no wiring changes needed.

### Step 4: Run tests to confirm Green
```bash
uv run pytest backend/tests/unit/test_dashboard_live_routes.py -x
```

All 8 tests must PASS.

### Step 5: Smoke test against running server
```bash
DEMO_MODE=1 uv run uvicorn backend.main:app --reload &
sleep 2
curl -sS http://localhost:8000/v1/dashboard/research/live | jq .
# Expected: {"active": [...], "last_cycle_at": "...", "now": "..."}
kill %1
```

### Step 6: Format and lint
```bash
uv run ruff format backend/presentation/api/routes/dashboard.py
uv run ruff check --fix backend/presentation/api/routes/dashboard.py
```

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_dashboard_live_routes.py -x
uv run ruff check backend/presentation/api/routes/dashboard.py
```

## Success Criteria

- 8/8 tests pass.
- Endpoint reachable at `GET /v1/dashboard/research/live` with no auth.
- `Cache-Control: no-store` on every response.
- `dynamic_search_limit` applied (30/min anon, 300/min auth).
- No new dependency.
- Existing dashboard endpoints still work (`/v1/dashboard/radar`, `/v1/dashboard/metrics`, `/v1/dashboard/research`).
