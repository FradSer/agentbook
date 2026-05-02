# Sprint Contract — Batch 5 (SSE Stream Endpoint)

**Plan:** `docs/plans/2026-05-01-live-research-banner-plan/`
**Batch:** 5 of 7
**Mode:** Linear Red/Green pair (009a → 009b)
**Code checklist:** `docs/retros/checklists/code-v1.md` (v1)

## Tasks in this batch

| Plan ID | TaskList ID | Subject | Depends-on |
|---|---|---|---|
| 009a | 13 | GET /v1/dashboard/research/stream SSE endpoint — Red | 007b ✓, 008b ✓ |
| 009b | 14 | GET /v1/dashboard/research/stream SSE endpoint — Green | 009a |

## Acceptance Criteria

### Task 009a — SSE stream tests (Red)
- File `backend/tests/unit/test_dashboard_stream_route.py` created with 13 test contracts:
  1. anonymous → 200 + `Content-Type: text/event-stream`
  2. first frame parses as `event: snapshot\n` with valid JSON `data:`
  3. `set_research_status(pid, True)` → next frame is `research_started`
  4. `set_research_status(pid, False)` → next frame is `research_ended`
  5. stale row falling out of 360 s window → emits `research_ended` via diff loop
  6. `:heartbeat ...\n\n` line after `HEARTBEAT_INTERVAL_SECONDS` (mock to small)
  7. `Last-Event-ID: 5` reconnect → server still sends `id: 0` snapshot
  8. `HARD_TIMEOUT_SECONDS=2` → connection closes cleanly after 2 s
  9. 6th concurrent stream from same IP returns 429 `{"error": "rate_limit_exceeded"}`
  10. payload allowlist EXACT keys: problem_id, description, solution_count, best_confidence, research_started_at, elapsed_seconds, now, last_cycle_at — NO agent_id, reporter_id, email, API keys, markdown
  11. each diff event produces structured log line `event=research_started`/`event=research_ended` with problem_id
  12. `last_cycle_at` MAX-query count ≤ 1 across 5 ticks within 10 s
  13. CORS allowlist echoes configured origin (never `*`)
- Tests use `httpx.AsyncClient.stream("GET", url)` and parse SSE frames by `\n\n` split.
- All 13 tests FAIL with 404 Not Found (route not registered) or `AttributeError` for cap test.
- No production code modified.

### Task 009b — SSE stream impl (Green)
- New constants in `backend/core/config.py`:
  - `POLL_INTERVAL_SECONDS: float = 2.0`
  - `HEARTBEAT_INTERVAL_SECONDS: float = 25.0`
  - `HARD_TIMEOUT_SECONDS: int = 15 * 60`
  - `LAST_CYCLE_CACHE_TTL_SECONDS: float = 10.0`
- New endpoint in `backend/presentation/api/routes/dashboard.py`:
  - `GET /v1/dashboard/research/stream`
  - Async handler with `Depends(get_optional_current_agent)` (so rate limiter knows about auth)
  - Limiter key: `agent.agent_id` if authenticated else `request.client.host`
  - Acquires `sse_limiter.acquire(key, authenticated=...)`; on `TooManyConcurrentStreams` returns `JSONResponse({"error": "rate_limit_exceeded"}, status_code=429)` BEFORE constructing the `StreamingResponse`
  - Uses `StreamingResponse(generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"})`
  - Inside generator:
    - Compute initial snapshot via `service.get_live_research_snapshot()`
    - Cache `last_cycle_at` with `(value, monotonic_ts)`; refresh when `monotonic() - ts > LAST_CYCLE_CACHE_TTL_SECONDS`
    - Emit `event: snapshot\nid: 0\ndata: {...}\n\n`
    - Track `last_active = {a["problem_id"]: a for a in snapshot["active"]}`
    - Loop while `monotonic() - started_at < HARD_TIMEOUT_SECONDS`:
      - `await asyncio.sleep(POLL_INTERVAL_SECONDS)`
      - Recompute snapshot using cache for `last_cycle_at`
      - Diff: emit `event: research_started` for new pids; `event: research_ended` for removed pids
      - Log structured `logger.info("sse_event", extra={"event": ..., "problem_id": pid, "now": ...})`
      - Every `HEARTBEAT_INTERVAL_SECONDS` emit `:heartbeat <iso-now>\n\n` (comment line)
  - `Last-Event-ID` is read but ignored — server starts fresh `id: 0` snapshot every connect.
  - Heartbeat is a comment line (`:heartbeat ...\n\n`), NOT a `data:` event.
- 13/13 tests in `test_dashboard_stream_route.py` PASS.
- Existing dashboard endpoints still work; existing 8 dashboard `/live` tests still pass.
- `uv run ruff check backend/presentation/api/routes/dashboard.py backend/core/config.py` exits 0.

## Code checklist v1 — items most relevant this batch

- **CODE-ASSUME-01 / 02**: grep for existing `Settings` class in `config.py`, `set_research_status` service method, `JSONResponse` patterns, `httpx.AsyncClient.stream` usage in any existing test (`grep -r "AsyncClient" backend/tests/`).
- **CODE-EDIT-01 / 02**: re-Read after `ruff format`. The 4 new config constants will be touched by ruff.
- **CODE-LINT-01**: `ruff check` on touched files.
- **CODE-TEST-01**: in-memory repos, no Docker.
- **CODE-TEST-03**: 009a Red FAILs with 404 (route missing), not collection errors.
- **CODE-VERIFY-01**: `make fast` after 009b — expect 453 → 466 passing (+13 stream tests).
- **CODE-VERIFY-02**: SSE handler is non-trivial async code — re-run full unit suite.
- **CODE-SCOPE-01**: 009a touches only the test file; 009b touches `dashboard.py` + `config.py`.

## Out-of-scope guards

- Do NOT add `sse_starlette` or any new dependency.
- Do NOT modify `backend/main.py` (route already wired via `dashboard.py`'s router).
- Do NOT touch frontend.
- Do NOT modify `service.py`, `schemas.py`, or any existing endpoint.

## Verification commands (per task)

### Task 009a
```bash
uv run pytest backend/tests/unit/test_dashboard_stream_route.py -x
# Expected: 13 FAILED tests, 404 (route missing)
```

### Task 009b
```bash
uv run pytest backend/tests/unit/test_dashboard_stream_route.py -x
# Expected: 13 PASSED
uv run ruff check backend/presentation/api/routes/dashboard.py backend/core/config.py
make fast
# Expected: 466 passed (453 baseline + 13 new stream tests)
```
