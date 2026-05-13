# Handoff State — Live Research Banner Plan

**Last updated:** Batch 5 complete (14 / 20 tasks done — 70%)

## Completed task IDs (plan IDs)
- 001 — BDD feature file landed (27 scenarios)
- 002 — Protocol additions; `RESEARCH_TIMEOUT_SECONDS = 360`
- 003 — Alembic migration for partial index
- 004a/004b — `list_being_researched` + `get_latest_cycle_at` (in-memory + SQLAlchemy)
- 005a/005b — `service.get_live_research_snapshot()` (10 tests)
- 006 — Pydantic schemas (`extra='forbid'`)
- 007a/007b — REST endpoint `GET /v1/dashboard/research/live` (8 tests)
- 008a/008b — `backend/core/sse_concurrency.py` (7 tests)
- 009a/009b — SSE endpoint `GET /v1/dashboard/research/stream` (13 tests; per-conn 2 s diff loop, heartbeat comments, 15-min timeout, concurrency-limiter integration)
- 010 — Frontend types + `fetchLiveResearchSnapshot()` helper

## Modified files (cumulative, 17 files)
- `backend/tests/features/live_research_banner.feature` (new)
- `backend/domain/repositories.py` (modified)
- `backend/application/service.py` (modified)
- `backend/infrastructure/persistence/sqlalchemy_models.py` (modified)
- `alembic/versions/c7bae2af560d_*.py` (new)
- `backend/tests/unit/test_in_memory_repos.py` (modified)
- `backend/tests/integration/test_sqlalchemy_repos.py` (modified)
- `backend/infrastructure/persistence/in_memory.py` (modified)
- `backend/infrastructure/persistence/sqlalchemy_repositories.py` (modified)
- `backend/tests/unit/test_sse_concurrency.py` (new)
- `backend/core/sse_concurrency.py` (new)
- `backend/tests/unit/test_service_live_research.py` (new)
- `backend/presentation/api/schemas.py` (modified)
- `backend/tests/unit/test_dashboard_live_routes.py` (new)
- `backend/presentation/api/routes/dashboard.py` (modified — `/research/live` + `/research/stream` + 2 helpers)
- `backend/core/config.py` (modified — 4 timing constants)
- `backend/tests/unit/test_dashboard_stream_route.py` (new)
- `frontend/lib/types.ts` (modified — `LiveResearchActive`, `LiveResearchSnapshot`)
- `frontend/lib/api.ts` (modified — `fetchLiveResearchSnapshot`)

## Test counts
- Pre-plan baseline: 423 passing
- After batch 5: **466 passing** (3 deselected). +43 over baseline. 0 regressions. Frontend tsc + biome clean (no frontend tests touched yet — those land in batch 6).

## Recurring Failure Patterns (from prior evaluation reports)
1. **Autoflake hook strips imports added but unused** (CODE-EDIT-01) — observed in batches 2, 4, 5. Mitigation: add the import + the consumer in a single Edit pass.
2. **NEW (from batch 5): ASGITransport buffers entire response — incremental SSE reads not possible**. Mitigation in test code: drain the entire generator (force a short `HARD_TIMEOUT_SECONDS` via `monkeypatch.setattr`) and assert on the accumulated buffer; mid-flight mutations must be scheduled via concurrent asyncio tasks.

## Architecture / API patterns to remember

- **Routes using rate limiters** (slowapi or sse_concurrency) need `Depends(get_optional_current_agent)` so `request.state.agent` is set for tier selection.
- **Per-connection 2 s poll-and-diff loop** in SSE handler — no shared bus.
- **`RESEARCH_TIMEOUT_SECONDS = 360`** — exported from `backend.application.service`.
- **Server-side time math for SQLAlchemy** — `func.now() - func.make_interval(secs=timeout_seconds)`.
- **SSE concurrency caps** in `backend/core/sse_concurrency.py`: 5 / 20 / 200; `acquire(key, *, authenticated=False)` is `@asynccontextmanager`; pre-acquire pattern is `cm.__aenter__()` outside generator + `cm.__aexit__` in generator's `finally`.
- **SSE stream contract** in `dashboard.py`:
  - Endpoint: `GET /v1/dashboard/research/stream`
  - First frame: `event: snapshot\nid: 0\ndata: {...}\n\n`
  - Diff frames: `event: research_started` / `event: research_ended` with `id: <N>`
  - Heartbeat: `:heartbeat <iso>\n\n` (comment line, NOT a data event)
  - `Last-Event-ID` is read but ignored
  - 4 timing constants in `backend.core.config` (POLL_INTERVAL_SECONDS=2.0, HEARTBEAT_INTERVAL_SECONDS=25.0, HARD_TIMEOUT_SECONDS=15*60, LAST_CYCLE_CACHE_TTL_SECONDS=10.0)
- **Reuse existing CSS tokens** — `.research-active`, `--research-glow-strong`, `.researching-dot`, `.researching-ping`, `Researching` badge variant.
- **`freezegun` is NOT a project dep** — use direct `timedelta` math + monkey-patch on constants.
- **Frontend lint**: project uses Biome (`pnpm lint` runs `biome check . && tsc --noEmit`).
- **`request<T>` helper in `frontend/lib/api.ts`** already passes `cache: "no-store"`.
- **Existing fetcher style** (`fetchRadar`, `fetchMetrics`) — model `fetchLiveResearchSnapshot` after these.

## Numeric constants
- 360 s research freshness window (`RESEARCH_TIMEOUT_SECONDS`)
- 2 s SSE poll tick (`POLL_INTERVAL_SECONDS`)
- 10 s last_cycle_at cache window (`LAST_CYCLE_CACHE_TTL_SECONDS`)
- 25 s heartbeat (`HEARTBEAT_INTERVAL_SECONDS`)
- 15 min hard timeout (`HARD_TIMEOUT_SECONDS`)
- 5 / 20 / 200 SSE concurrency caps
- 30 / 300 per minute REST rate limit
- 60 s reopen probe in fallback (frontend — batch 6)
- 3 consecutive errors triggers fallback (frontend — batch 6)
- 1 s initial backoff (frontend — batch 6)

## Coordinator-stall lessons (3 stalls so far)
- Two batch coordinators stalled mid-batch (batches 2 first attempt, 4 first attempt). Recovery pattern works.
- Tighten coordinator prompts: explicit per-task step caps, "always return structured result", granular task ordering.
- Pre-warn coordinators about: autoflake import stripping, test fixture name conventions, optional auth dep requirement, ASGITransport buffering for SSE tests.

## Notes for batch 6 (011a/b — useLiveResearch hook + 012a/b — LiveResearchBanner)

- **Two parallel Red/Green pairs** in this batch, both frontend-only:
  - Pair A: 011a (hook tests, 14 cases) → 011b (hook impl, ~60 LOC)
  - Pair B: 012a (component tests, 18 cases) → 012b (component impl, ~120 LOC)
- 012b depends on BOTH 012a (test) AND 011b (hook impl) — so order: 011a → 011b → 012a → 012b. Could also do 011a → 012a (parallel test writes) → 011b → 012b but the additional parallelism saves only ~2 calls and adds risk.
- **jsdom does NOT ship `EventSource`** — install `MockEventSource` stub via `vitest.setup.ts` (or `frontend/vitest.setup.ts`). Pattern in 011a task file.
- **Use `vi.useFakeTimers()`** for deterministic 10 s poll, 60 s reopen probe, 1 s aria-live debounce assertions.
- **Mock `useLiveResearch`** per-test in 012a using `vi.mock("@/lib/use-live-research", ...)` — no need to drive the real hook from component tests.
- **Reuse `Badge variant="researching"`, `Card`, `.research-active`, `.researching-dot`, `TitleMarkdown`, `focusRing`, `getRelativeTime`, `getConfidenceTier`, `cn`** — ALL already exist in the repo. Grep for these before importing.
- **Aria-live debounce**: 1 s debounce on the announcement region. Two transitions within 500 ms → 1 announce.
- **Fallback hint**: render quiet `(reconnecting)` text — NOT an `<Alert>` (per design calm-tone constraint).
- **No new CSS custom properties.** Verify via `grep -r "var(--research-" frontend/components/app/live-research-banner.tsx` shows only existing names.
