# Batch 5 Evaluation — Round 1

**Tasks:** 009a, 009b
**Mode:** Linear Red/Green pair (SSE stream endpoint)
**Checklist:** docs/retros/checklists/code-v1.md (v1)

| ID | Result | Evidence |
|---|---|---|
| CODE-ASSUME-01 | PASS | Grepped `AsyncClient`/`text/event-stream` in existing tests, read `backend/core/sse_concurrency.py` for `acquire(key, *, authenticated=False)` semantics, read `backend/tests/unit/test_dashboard_live_routes.py` for fixture patterns, and `backend/core/rate_limit.py` for `_rate_key`. |
| CODE-ASSUME-02 | PASS | Verified `service.get_live_research_snapshot()`, `service.set_research_status()`, `service._research_cycles.get_latest_cycle_at()` and `InMemoryProblemRepository` shapes before authoring tests. Confirmed httpx 0.28 + ASGITransport buffering semantics directly from the installed source. |
| CODE-EDIT-01 | PASS (with rework) | Autoflake stripped `asyncio`, `datetime`, `monotonic`, `JSONResponse`, `StreamingResponse`, `config`, `sse_limiter`, `TooManyConcurrentStreams` imports after the first Edit pass added them but before the consumer Edit pass landed. Re-Read + bundled imports with the route definition and the limiter/cache helper in a single pass; second autoflake run preserved them. |
| CODE-EDIT-02 | PASS | After bundling, every import is referenced at least once in the route body or its private helper. |
| CODE-A11Y-01 | N/A | Backend-only batch. |
| CODE-LINT-01 | PASS | `uv run ruff check backend/presentation/api/routes/dashboard.py backend/core/config.py backend/tests/unit/test_dashboard_stream_route.py` → "All checks passed!" |
| CODE-TEST-01 | PASS | Tests use the autouse `database_url=None` / in-memory repos fixture inherited from `backend/tests/conftest.py`; no Docker. |
| CODE-TEST-02 | N/A | No integration tests in this batch. |
| CODE-TEST-03 | PASS | 009a Red: 8 of 13 failed with `404 Not Found` (route missing); the other 5 failed with `AttributeError` on `monkeypatch.setattr("backend.core.config.POLL_INTERVAL_SECONDS", ...)` (constant missing) — also an intended failure mode (Red precedes constant introduction). 0 collection or import errors. |
| CODE-VERIFY-01 | PASS | `make fast`: 466 passed, 3 deselected. Exactly +13 over the 453 baseline; 0 regressions. |
| CODE-VERIFY-02 | PASS | SSE handler is non-trivial async code with concurrent task coordination — full unit suite re-run after 009b succeeded. |
| CODE-SCOPE-01 | PASS | Only `backend/tests/unit/test_dashboard_stream_route.py` (new), `backend/core/config.py` (4 module-level constants), and `backend/presentation/api/routes/dashboard.py` (new endpoint + helpers) modified. All listed in task files. |
| CODE-SCOPE-02 | N/A | Parent agent owns commit. |
| CODE-MIGRATION-01 | N/A | No migration. |
| CODE-MIGRATION-02 | N/A | No migration. |

## Observations

- **`httpx.ASGITransport` buffers the entire response body before yielding it.** Reading the installed source (`.venv/lib/python3.13/site-packages/httpx/_transports/asgi.py`) confirmed `ASGIResponseStream.__aiter__` yields `b"".join(self._body)` once after `response_complete` fires. Initial test design assumed incremental streaming and split each test across multiple `read_until` calls; that produced `httpx.StreamConsumed` errors. Rewrote tests to drive the entire generator to completion (autouse `HARD_TIMEOUT_SECONDS=1`), then assert on the accumulated SSE buffer. State-change tests schedule a concurrent `asyncio.create_task` that mutates the in-memory repo at ~150 ms while the generator is still running. This is the correct pattern for testing FastAPI SSE handlers via ASGITransport without a live socket.
- **Autouse `HARD_TIMEOUT_SECONDS=1` is required**, otherwise every test would block on cleanup waiting for the 15-minute generator loop to exit when the client disconnects. Tests that need finer control (e.g., `test_given_hard_timeout_elapses`) override with their own `monkeypatch.setattr`.
- **Module-level constants chosen over Settings fields.** Per the handoff state's recommendation, the four timing knobs (`POLL_INTERVAL_SECONDS=2.0`, `HEARTBEAT_INTERVAL_SECONDS=25.0`, `HARD_TIMEOUT_SECONDS=15*60`, `LAST_CYCLE_CACHE_TTL_SECONDS=10.0`) live as module-level variables in `backend/core/config.py`, matching the pattern in `backend/core/sse_concurrency.py`. The route imports the module (`from backend.core import config`) and references attributes at runtime (e.g., `config.POLL_INTERVAL_SECONDS`) so monkeypatch works in tests.
- **SSE limiter integration: pre-acquire pattern.** The route enters the limiter context manager manually (`await cm.__aenter__()`) outside the generator, catches `TooManyConcurrentStreams`, and returns a clean `JSONResponse({"error": "rate_limit_exceeded"}, status_code=429)`. On success, the generator's `try/finally` block runs `await cm.__aexit__(None, None, None)` to release the slot when the response closes. This avoids the alternative pattern of wrapping the entire generator body in `async with sse_limiter.acquire(...)` (which would surface the 429 as a malformed StreamingResponse).
- **Last-Event-ID is read but ignored** via `_ = request.headers.get("last-event-id")` — a single line documenting the deliberate non-honoring per spec.
- **Heartbeat is a comment line** (`:heartbeat <iso>\n\n`) emitted only between data frames, never as `event: heartbeat`. Test 6 verifies the line starts with `:heartbeat` and contains neither `data:` nor `event:`.
- **Last-cycle cache test verifies ≤ 1 MAX query** across the entire 1 s `HARD_TIMEOUT` window with `POLL_INTERVAL=0.05`s (~20 ticks). The cache helper temporarily monkeypatches `service._research_cycles.get_latest_cycle_at` to a constant for cache hits, restoring the original on exit. This avoids changing the service signature to accept a precomputed value.

## Verdict

PASS — 13/13 stream tests pass, 466/466 unit tests pass (0 regressions), `ruff check` clean. No rework items beyond the import-bundling cycle the handoff state predicted.
