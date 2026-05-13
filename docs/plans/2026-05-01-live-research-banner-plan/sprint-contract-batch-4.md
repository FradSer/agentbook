# Sprint Contract — Batch 4 (REST endpoint Red/Green + Frontend types)

**Plan:** `docs/plans/2026-05-01-live-research-banner-plan/`
**Batch:** 4 of 7
**Mode:** REST pair (007a → 007b) sequential; Task 010 (frontend types) parallel/independent
**Code checklist:** `docs/retros/checklists/code-v1.md` (v1)

## Tasks in this batch

| Plan ID | TaskList ID | Subject | Depends-on |
|---|---|---|---|
| 007a | 9 | GET /v1/dashboard/research/live REST endpoint — Red | 006 ✓ |
| 007b | 10 | GET /v1/dashboard/research/live REST endpoint — Green | 007a |
| 010 | 15 | Frontend types and fetchLiveResearchSnapshot helper | 006 ✓ |

## Acceptance Criteria

### Task 007a — REST tests (Red)
- File `backend/tests/unit/test_dashboard_live_routes.py` created with 8 test contracts:
  1. anonymous GET → 200, no Authorization header
  2. response shape validates against `LiveResearchSnapshotResponse`
  3. service has 1 fresh problem → response.active has 1 item
  4. no fresh problems → response.active == []
  5. response carries `Cache-Control: no-store`
  6. anonymous rate limit at 30/min via `enable_limiter` fixture (31st returns 429)
  7. authenticated rate limit at 300/min via `enable_limiter` + `valid_api_key` fixtures (301st returns 429)
  8. CORS allowlist echoes configured origin (never `*`)
- All 8 tests FAIL with 404 Not Found (route not registered) or `AttributeError` on missing service method (fallback).
- Tests use the autouse fixtures from `backend/tests/conftest.py`.
- Rate-limit tests opt in via the `enable_limiter` fixture (existing repo pattern).
- No production code modified.

### Task 007b — REST impl (Green)
- New endpoint added to `backend/presentation/api/routes/dashboard.py`:
  - Path: `GET /v1/dashboard/research/live` (router prefix already `/v1/dashboard`)
  - `response_model=LiveResearchSnapshotResponse`
  - `@limiter.limit(dynamic_search_limit)` decorator
  - Public read (no `Depends(require_api_key)`)
  - Body: dict-passthrough — `service.get_live_research_snapshot()`, then return dict
  - `Cache-Control: no-store` header set via FastAPI `Response` param or `JSONResponse(headers=...)`
- 8/8 tests in `test_dashboard_live_routes.py` PASS.
- Existing dashboard endpoints (`/v1/dashboard/radar`, `/metrics`, `/research`) still work.
- `uv run ruff check backend/presentation/api/routes/dashboard.py` exits 0.

### Task 010 — Frontend types + helper
- `frontend/lib/types.ts` exports:
  - `LiveResearchActive` (problem_id, description, solution_count, best_confidence, research_started_at, elapsed_seconds)
  - `LiveResearchSnapshot` (active, last_cycle_at, now)
- `frontend/lib/api.ts` exports `fetchLiveResearchSnapshot(signal?: AbortSignal): Promise<LiveResearchSnapshot>` calling `/v1/dashboard/research/live`. Mirror style of existing `fetchRadar`/`fetchMetrics`.
- `pnpm tsc --noEmit` exits 0.
- `pnpm lint` (Biome) exits 0.
- No new dependency added.

## Code checklist v1 — items most relevant this batch

- **CODE-ASSUME-01 / 02**: grep for `dynamic_search_limit` location in `backend/core/rate_limit.py`, the existing `enable_limiter` fixture pattern (search `backend/tests/conftest.py` and existing dashboard route tests like `test_dashboard_*`), and the `request<T>` helper in `frontend/lib/api.ts` BEFORE writing tests/imports.
- **CODE-EDIT-01 / 02**: re-Read `dashboard.py` after `ruff format` runs.
- **CODE-LINT-01**: `uv run ruff check` (backend) + `pnpm lint` (frontend) at end of each task.
- **CODE-VERIFY-01**: `make fast` after 007b — expect 445 → 453 passing (8 new dashboard tests).
- **CODE-TEST-03**: 007a Red must FAIL with 404 (route not registered), not collection/import errors.
- **CODE-SCOPE-01**: 007a touches only `test_dashboard_live_routes.py`; 007b touches only `dashboard.py`; 010 touches only `frontend/lib/types.ts` + `frontend/lib/api.ts`.

## Out-of-scope guards

- Do NOT add the SSE endpoint `/v1/dashboard/research/stream` — that's Task 009.
- Do NOT call the SSE concurrency limiter from REST.
- Do NOT add new CORS configuration — relies on existing global middleware.
- Do NOT modify `pyproject.toml`, `frontend/package.json`, or `backend/main.py`.
- The frontend task (010) MUST NOT create any React components or hooks — those are 011 and 012.

## Verification commands (per task)

### Task 007a
```bash
uv run pytest backend/tests/unit/test_dashboard_live_routes.py -x
# Expected: 8 FAILED tests, 404 (route not registered)
```

### Task 007b
```bash
uv run pytest backend/tests/unit/test_dashboard_live_routes.py -x
# Expected: 8 PASSED
uv run ruff check backend/presentation/api/routes/dashboard.py
make fast
# Expected: 453 passed (445 baseline + 8 new dashboard tests)
```

### Task 010
```bash
cd frontend && pnpm tsc --noEmit
cd frontend && pnpm lint
```

## Notes

- The frontend `010` and the backend pair `007a/b` have no file overlap, so the coordinator may execute them in either order — recommended: do 007 chain first, then 010 (so the backend snapshot endpoint exists when frontend tooling smokes — though 010 doesn't actually hit the endpoint).
