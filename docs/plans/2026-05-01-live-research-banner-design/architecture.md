# Live Research Banner — Architecture

This document specifies the system-level design: verified constraints, the
chosen agent-to-API event-hop strategy, the file-level change plan, the SSE
protocol shape, rate-limit numbers, the idle-state data source, and a risk
register.

The verified file paths and line numbers below were re-derived from the
working tree at `/Users/FradSer/Developer/FradSer/agentbook` on 2026-05-01.

## 0. Verified facts (the constraints)

- **Two processes, same database.** The agent runs as a separate Railway
  service via the `RAILWAY_SERVICE_TYPE` switch in
  `railway.toml:7`; agent start command is
  `uv run -m agent.src.main`, API start command is
  `uv run uvicorn backend.main:app …`. They share `DATABASE_URL` and
  no other channel.
- **Status mutation point.** `service.set_research_status(UUID, bool)`
  at `backend/application/service.py:2042-2054` writes
  `Problem.research_started_at = utc_now() | None` and calls
  `self._problems.update(current)`. Called by
  `agent/src/research_loop.py:94, 192, 235, 293`.
- **"Researching" is a time-windowed flag, not a column.**
  `_is_being_researched(problem, timeout_seconds=360)` at
  `backend/application/service.py:2391-2396` is the canonical reader.
  A stale `research_started_at` (> 360 s) is implicitly idle without
  any explicit DB write.
- **The `research_started_at` column has no index today.** Added in
  `alembic/versions/7e8a50adfe56_add_research_started_at_to_problems.py`;
  ORM model at
  `backend/infrastructure/persistence/sqlalchemy_models.py:126`.
- **Sync DB driver only.** `psycopg2-binary 2.9.12`. No asyncpg in
  `pyproject.toml` or `uv.lock`.
- **Single uvicorn process today.** No `--workers` flag in
  `railway.toml`. But `mcp_stateless=True` in
  `backend/core/config.py:47` declares horizontal-scaling intent.
- **No SSE / WebSocket / EventSource code anywhere.** Confirmed by
  grep. The only `text/event-stream` references are MCP-transport
  client validation in
  `backend/presentation/mcp/streamable_router.py:67-71`, which is
  unrelated.
- **Existing rate-limit pattern.** `slowapi` with `dynamic_search_limit`
  in `backend/core/rate_limit.py` returns
  `300/minute` for authenticated agents, `30/minute` for anonymous IPs.
  `/v1/auth/register` uses a fixed `10/hour`.
- **No "list problems being researched" repo method.**
  `find_research_candidates` on the Problem repo
  (`backend/infrastructure/persistence/sqlalchemy_repositories.py:369`)
  picks **next** candidates and does not filter on
  `research_started_at`.

## 1. Recommendation — per-connection async poll inside the SSE handler

Each SSE handler runs its own 2-second poll loop, computes a diff against
the previous snapshot, and yields `research_started` / `research_ended`
events on transition. No shared state, no event bus, no broadcast.

### Rationale

1. **Match complexity to scale.** Today's load is single-digit
   concurrent homepage viewers; the agent toggles research on/off a few
   times per minute. A 2-second poll is `0.5 qps × N_connections`. With
   50 concurrent viewers that is 25 qps of a partial-indexed point
   lookup — well below the noise floor of a Railway Postgres.
2. **No new infrastructure.** All four alternatives needed something
   the project does not have:
   - **PostgreSQL `LISTEN/NOTIFY`** would force asyncpg as a parallel
     async driver alongside psycopg2 (psycopg2's sync `LISTEN` blocks
     a worker thread; an async LISTEN needs a dedicated thread + select
     loop or a separate driver). It also requires a trigger migration
     on `problems`, doubling the failure surface for every future
     write to that table. CLAUDE.md explicitly rejects "abstraction
     layers for two variants".
   - **Redis pub/sub** is plainly overkill given the project runs
     without Redis today.
   - **Centralised internal poller** is structurally fine but introduces
     a per-process singleton with broadcast fan-out, a bus abstraction,
     and lifecycle wiring into `_lifespan`. That is real complexity for
     the same observable outcome.
3. **Quieter by default** (`.impeccable.md`). One small handler, one
   query, one diff loop — no background task, no shared state, no
   startup hook.
4. **Horizontal-scale safe.** Each uvicorn worker independently polls
   the DB; clients connect to whichever worker the load balancer
   picks. No coordination needed because the DB is the single source
   of truth. Sticky sessions are irrelevant.
5. **Backpressure is automatic.** FastAPI's `StreamingResponse`
   buffers, and the underlying `asyncio.sleep(2)` paces the producer.
   No queues to drain.

### Promotion path

If concurrent SSE connections per worker ever exceed ~200 or research
toggles ever exceed ~10 Hz, promote to a per-process centralised poller
by extracting the diff loop into an `asyncio.Task` started in
`_lifespan` and fanning out via `asyncio.Queue`. That refactor is
local to the SSE handler — nothing in its public signature changes.

### What we explicitly are not doing

- Not adding `pg_notify` triggers.
- Not adding asyncpg as a parallel async driver.
- Not introducing a Redis dependency.
- Not implementing per-client `Last-Event-ID` replay across reconnects.

## 2. File plan

All paths below were verified against the working tree. Files marked
**NEW** do not currently exist.

### Backend

| Path | Status | Responsibility |
|---|---|---|
| `backend/domain/repositories.py` | modify | Add `list_being_researched(timeout_seconds: int = 360) -> list[Problem]` to the `ProblemRepository` Protocol. Add `get_latest_cycle_at() -> datetime | None` to the `ResearchCycleRepository` Protocol. Pure interfaces, no implementation. |
| `backend/infrastructure/persistence/sqlalchemy_repositories.py` | modify | Implement `list_being_researched`: `SELECT … FROM problems WHERE research_started_at IS NOT NULL AND research_started_at > now() - interval '<timeout>s' ORDER BY research_started_at DESC`. Returns domain `Problem` list via existing `_to_problem_domain`. Implement `get_latest_cycle_at` as `SELECT MAX(created_at) FROM research_cycles`. |
| `backend/infrastructure/persistence/in_memory.py` | modify | Mirror impls: list-comp filter for the former; `max((c.created_at for c in self._items.values()), default=None)` for the latter. |
| `backend/application/service.py` | modify | Add `get_live_research_snapshot() -> dict`. Returns `{"active": [{"problem_id", "description", "best_confidence", "solution_count", "research_started_at", "elapsed_seconds"}], "last_cycle_at": iso8601 \| None, "now": iso8601}`. Reuses the existing `_is_being_researched` semantics. Promote the literal `360` to a module-level constant `RESEARCH_TIMEOUT_SECONDS` and import it from both the helper and the new repo method. |
| `backend/presentation/api/routes/dashboard.py` | modify | Add `GET /v1/dashboard/research/live` (REST snapshot) and `GET /v1/dashboard/research/stream` (SSE). Both are anonymous. The SSE handler holds the per-connection 2 s poll loop. |
| `backend/presentation/api/schemas.py` | modify | Add `LiveResearchSnapshotResponse` and `LiveResearchActiveItem`. Used by the REST endpoint and the SSE `snapshot` event payload. |
| `backend/core/sse_concurrency.py` | **NEW** | Per-IP / per-agent concurrency semaphore for the SSE endpoint. Keeps `rate_limit.py` purely about slowapi qps. ~40 LOC. |
| `alembic/versions/<NEW>_add_problems_research_started_at_index.py` | **NEW** | `CREATE INDEX CONCURRENTLY ix_problems_research_started_at ON problems (research_started_at) WHERE research_started_at IS NOT NULL;`. Partial because the column is mostly NULL. Add the matching `index=True` on the ORM column for parity in dev. **Rollback note**: `CREATE INDEX CONCURRENTLY` leaves an `INVALID` index if interrupted; the migration's `down_revision` (and any retry pre-flight) must run `DROP INDEX IF EXISTS ix_problems_research_started_at;` before re-attempting. Document this in the migration's docstring. |

### Frontend

| Path | Status | Responsibility |
|---|---|---|
| `frontend/components/app/live-research-banner.tsx` | **NEW** | The banner component. Active state shows the most-recently-started problem's title (linked to `/memories/{id}`), `solution_count`, `best_confidence` percent badge, and "started Xs ago" sublabel; idle state shows `"Idle · last cycle Xm ago"`. Uses `Badge variant="researching"`, `Card`-shaped surface with `research-active` class for the pulse glow, `TitleMarkdown` (dynamic-imported), `focusRing` on the link, and `Skeleton` during initial fetch. |
| `frontend/lib/use-live-research.ts` | **NEW** | Hook returning `{ snapshot, status }` where `status: "loading" \| "open" \| "fallback" \| "error"`. Owns the `EventSource`, exponential-backoff reconnect (delegated to native `EventSource`), and fallback to `fetchLiveResearchSnapshot()` REST polling on three consecutive failures. ~60 LOC. |
| `frontend/lib/api.ts` | modify | Add `fetchLiveResearchSnapshot(): Promise<LiveResearchSnapshot>` mirroring `fetchRadar` style. |
| `frontend/lib/types.ts` | modify | Add `LiveResearchActive` and `LiveResearchSnapshot` types. |
| `frontend/app/page.tsx` | modify | Render `<LiveResearchBanner />` between the hero header (lines 540-556) and the `<Tabs>` block (line 563). No prop drilling — banner is self-contained. |
| `frontend/app/globals.css` | unchanged | Tokens `--research-glow-strong/-soft`, `.researching-dot`, `.researching-ping`, `.research-active`, `@keyframes research-pulse`, and the `prefers-reduced-motion` media rule (lines 47-48, 312-355) all already exist. **Do not** add new tokens. |

### Tests

| Path | Status | Responsibility |
|---|---|---|
| `backend/tests/unit/test_service_live_research.py` | **NEW** | Unit tests for `service.get_live_research_snapshot`: empty state (`active=[]`, `last_cycle_at=None`); single active problem; stale `research_started_at` (> 360 s) treated as inactive; with research history. Uses in-memory repos. |
| `backend/tests/unit/test_dashboard_live_routes.py` | **NEW** | FastAPI `TestClient` for `GET /v1/dashboard/research/live` (assert shape, 200, no auth required) and `GET /v1/dashboard/research/stream` (assert `Content-Type: text/event-stream`, parse first emitted `event: snapshot`, then drive a state change via `service.set_research_status` and assert the next chunk contains `event: research_started`). Test the per-IP concurrency cap via the `enable_limiter` fixture. |
| `backend/tests/unit/test_in_memory_repos.py` | modify | Add cases for `list_being_researched` and `get_latest_cycle_at`. |
| `backend/tests/integration/test_sqlalchemy_repos.py` | modify | Add cases for the same two methods against real Postgres. |
| `backend/tests/features/live_research_banner.feature` | **NEW** | The Gherkin contract. See `bdd-specs.md`. |
| `frontend/tests/live-research-banner.test.tsx` | **NEW** | vitest + jsdom. Mock `EventSource` (jsdom does not ship it; write a tiny stub class with `addEventListener` and a manual `dispatch`). Assert: skeleton on load → `Researching` badge appears on `research_started` event → `Idle · last cycle Xm ago` on `research_ended` event → graceful fallback to `fetchLiveResearchSnapshot` after three `onerror` events. |

## 3. SSE protocol shape

### Endpoint

`GET /v1/dashboard/research/stream` — anonymous (matches `/v1/search`).

Response headers:

- `Content-Type: text/event-stream; charset=utf-8`
- `Cache-Control: no-cache, no-transform`
- `X-Accel-Buffering: no` — defensive against Railway-edge SSE buffering
- `Connection: keep-alive`

### Event vocabulary

Three event types plus heartbeat. All `data:` payloads are JSON. Each
event carries a monotonic `id:` line, used only by browser plumbing —
the server does **not** honour `Last-Event-ID` on reconnect (clients
re-subscribe and the server starts with a fresh `snapshot`).

```
event: snapshot
id: 0
data: {
  "active": [
    {
      "problem_id": "0a4f…",
      "description": "Docker container exit code 137 OOM",
      "solution_count": 4,
      "best_confidence": 0.78,
      "research_started_at": "2026-05-01T12:34:56Z",
      "elapsed_seconds": 12
    }
  ],
  "last_cycle_at": "2026-05-01T12:33:00Z",
  "now": "2026-05-01T12:35:08Z"
}

event: research_started
id: 1
data: {
  "problem_id": "0a4f…",
  "description": "Docker container exit code 137 OOM",
  "solution_count": 4,
  "best_confidence": 0.78,
  "research_started_at": "2026-05-01T12:34:56Z",
  "now": "2026-05-01T12:35:08Z"
}

event: research_ended
id: 2
data: {
  "problem_id": "0a4f…",
  "last_cycle_at": "2026-05-01T12:36:42Z",
  "now": "2026-05-01T12:36:42Z"
}

:heartbeat 2026-05-01T12:36:42Z
```

`research_ended` carries the freshly-recomputed `last_cycle_at` so the
banner can switch immediately from "Researching …" to "Idle · last cycle
0s ago" without an extra fetch.

The heartbeat is a **comment line** (`:heartbeat …\n\n`), not a `data:`
event. Comment lines do not invoke the client's `onmessage` handler so
heartbeats cause no UI re-render. Their sole purpose is to defeat
intermediate proxy idle-timeouts.

### Connection lifecycle (server side, pseudo-Python)

```python
RESEARCH_TIMEOUT_SECONDS = 360
POLL_INTERVAL_SECONDS = 2.0
HEARTBEAT_INTERVAL_SECONDS = 25.0
HARD_TIMEOUT_SECONDS = 15 * 60

async def event_stream():
    started_at = monotonic()
    last_heartbeat = started_at

    snapshot = service.get_live_research_snapshot()
    yield _format_event("snapshot", snapshot)
    last_active: dict[str, dict] = {a["problem_id"]: a for a in snapshot["active"]}

    while monotonic() - started_at < HARD_TIMEOUT_SECONDS:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        snap = service.get_live_research_snapshot()
        current_active = {a["problem_id"]: a for a in snap["active"]}

        for pid in current_active.keys() - last_active.keys():
            yield _format_event(
                "research_started",
                current_active[pid] | {"now": snap["now"]},
            )
        for pid in last_active.keys() - current_active.keys():
            yield _format_event(
                "research_ended",
                {
                    "problem_id": pid,
                    "last_cycle_at": snap["last_cycle_at"],
                    "now": snap["now"],
                },
            )

        last_active = current_active

        if monotonic() - last_heartbeat > HEARTBEAT_INTERVAL_SECONDS:
            yield f":heartbeat {snap['now']}\n\n"
            last_heartbeat = monotonic()
```

### Heartbeat

`:heartbeat <iso-now>\n\n` every **25 s**. Three purposes: (1) defeats
intermediate proxy idle timeouts (Railway edge defaults sit around
60-100 s, Cloudflare and ALB at 30-60 s); (2) keeps `EventSource`
healthy; (3) is invisible to `onmessage`, so no UI re-renders.

### Hard 15-minute server timeout

The server closes the connection after 15 minutes regardless of state.
`EventSource` reconnects transparently. This bounds memory if a client
process dies without closing TCP and prevents long-lived workers from
accumulating zombie connections.

### Client reconnect / fallback

`EventSource` has built-in exponential-backoff reconnect on connection
loss; the hook does not layer its own retry on top. Instead:

- After **three consecutive `onerror` events without an intervening
  `onmessage`**, the hook falls back to **REST polling**
  (`fetchLiveResearchSnapshot()` on a 10 s interval). This is the safety
  net for environments where SSE is blocked (corporate proxies, some
  mobile networks).
- The hook **periodically tries to re-open the EventSource every 60 s**
  while in REST-fallback mode. On the first successful `snapshot`
  event it cancels the REST interval.

While in fallback mode the banner shows a small `(reconnecting)` hint
in the corner — no destructive alert, no flash.

### Why no `Last-Event-ID` replay

The DB is the source of truth. On reconnect the server re-emits a fresh
`snapshot`, which by construction is correct regardless of what the
client missed. Implementing a per-connection event log just to support
`Last-Event-ID` would be at least an order of magnitude more code for
zero observable benefit.

## 4. Existing patterns to reuse

| Pattern | Path | Reuse note |
|---|---|---|
| `_is_being_researched(problem, timeout_seconds=360)` | `backend/application/service.py:2391` | Reuse verbatim. Promote the literal 360 to `RESEARCH_TIMEOUT_SECONDS` so both call sites and the new repo method import it. |
| Existing `is_being_researched` consumers | `backend/application/service.py:625, :793, :2384` | Three existing consumers prove the timeout-window semantics are stable. The banner is the fourth. |
| Dashboard endpoint pattern | `backend/presentation/api/routes/dashboard.py` | Mirror style: `APIRouter(prefix="/v1/dashboard", tags=["dashboard"])`, `service: AgentbookService = Depends(get_service)`, dataclass-style response model. The new endpoints land in this same router. |
| Research CSS tokens | `frontend/app/globals.css:43-48, :312-355` | Use `var(--research-glow-strong)`, `.research-active`, `.researching-dot`, `.researching-ping`, the `research-pulse` keyframes, and the `prefers-reduced-motion` rule. **Do not** add new colour tokens. |
| `Researching` badge variant | `frontend/components/ui/badge.tsx:37-39` | Already wired to `--research-bg/-fg/-border`. Use `<Badge variant="researching">Researching</Badge>` — same as existing problem cards at `app/page.tsx:200-208`. |
| Existing 30 s radar polling pattern | `frontend/app/page.tsx:521-528` | Pattern reference for the REST fallback poller in `useLiveResearch`. |
| `TitleMarkdown` for problem description | `frontend/app/page.tsx:81-94` | Reuse the dynamic-import pattern with the `LoadingSpinner` fallback. |
| API helper style | `frontend/lib/api.ts:67-73` (`fetchRadar`/`fetchMetrics`) | Mirror for `fetchLiveResearchSnapshot`. |
| Slowapi limiter with dynamic key | `backend/core/rate_limit.py` + `backend/presentation/api/routes/search.py:30-31` | The REST snapshot endpoint reuses `dynamic_search_limit` — no new tier. |
| `enable_limiter` test fixture | `backend/tests/conftest.py` | Opt-in for rate-limit tests. |
| `getRelativeTime`, `getConfidenceTier`, `cn` | `frontend/lib/utils.ts` | Reuse for sublabels and the percent badge tier. |
| `focusRing` | `frontend/lib/focus-ring.ts` | Reuse on the clickable problem-title link. |

## 5. Endpoints + rate limiting

### `GET /v1/dashboard/research/live` — REST snapshot

- **Auth.** Anonymous. Public-read posture.
- **Rate limit.** Reuses `@limiter.limit(dynamic_search_limit)` →
  30/min anonymous (by IP), 300/min authenticated (by `agent_id`). No
  new tier.
- **Response.** `LiveResearchSnapshotResponse` — same shape as the
  SSE `snapshot` event payload (see §3).
- **Caching.** `Cache-Control: no-store`. Data is real-time by
  definition.

### `GET /v1/dashboard/research/stream` — SSE long-poll

- **Auth.** Anonymous (native `EventSource` cannot send custom
  headers, which is fine because reads are public).
- **Rate limit.** Separate concurrency cap, **not** slowapi qps. SSE
  is one long request, so qps-based throttling is meaningless.
  Implementation lives in the new module
  `backend/core/sse_concurrency.py`:
  - **5 concurrent connections per anonymous IP.** Tolerates dev
    tooling, multiple tabs, mobile + desktop, and curl debugging
    without permitting trivial DoS.
  - **20 concurrent connections per authenticated agent** (rare for
    this banner, but allowed for parity).
  - **200 total concurrent streams per worker.** If exceeded, return
    `503 too_many_streams`. Protects the worker event loop from
    starvation.
  - **15-minute hard server-side timeout** — `EventSource` reconnects
    transparently. Bounds memory if a client process dies without
    closing TCP.
- Implementation: `defaultdict[str, int]` keyed on remote address (or
  `agent_id` when authenticated), guarded by an `asyncio.Lock`.
  Increment on connect, decrement in `finally`.

### Limit summary

| Endpoint | Auth | Limit | Source |
|---|---|---|---|
| `GET /v1/dashboard/research/live` | none | 30/min by IP, 300/min by agent | reuses `dynamic_search_limit` |
| `GET /v1/dashboard/research/stream` | none | 5 concurrent per IP, 200 per worker, 15-min hard cap | new `core/sse_concurrency.py` |
| `GET /v1/dashboard/research/stream` | authed | 20 concurrent per agent | new `core/sse_concurrency.py` |

## 6. Idle-state data — where "last cycle Xm ago" comes from

**Source: `MAX(research_cycles.created_at)`** via a new
`ResearchCycleRepository.get_latest_cycle_at()` method.

`research_cycles.created_at` is the canonical "an agent did something"
timestamp. Every successful proposal, every skip, every synthesis writes
a row:

- improved path: `agent/src/research_loop.py:415-426`
- no-solution-proposed path: `agent/src/research_loop.py:156-163,
  :171-177, :181-189`
- skip path: `agent/src/research_loop.py:155-163`

The existing repo already orders by `created_at`
(`sqlalchemy_repositories.py:615, :642`) and exposes
`get_last_researched_at(problem_id)` per-problem at `:630-635`. We need
the global MAX, which is a one-line addition.

### Alternatives considered and rejected

- **`MAX(problems.research_started_at)`.** Misses cycles where the
  agent finished and reset to NULL, and misses cycles where
  `set_research_status` was bypassed (skip paths do not always set
  it). Underreports.
- **`solutions.created_at`.** Only covers the "improved" path.
  Underreports.
- **`outcomes.created_at`.** Includes manual user reports, not just
  agent activity. Overreports.

### The service method

```python
def get_live_research_snapshot(self) -> dict:
    active = self._problems.list_being_researched(
        timeout_seconds=RESEARCH_TIMEOUT_SECONDS
    )
    last_cycle_at = (
        self._research_cycles.get_latest_cycle_at()
        if self._research_cycles is not None
        else None
    )
    now = utc_now()
    return {
        "active": [
            {
                "problem_id": str(p.problem_id),
                "description": p.description[:300],
                "solution_count": p.solution_count,
                "best_confidence": p.best_confidence,
                "research_started_at": p.research_started_at.isoformat(),
                "elapsed_seconds": int(
                    (now - p.research_started_at).total_seconds()
                ),
            }
            for p in active
        ],
        "last_cycle_at": (
            last_cycle_at.isoformat() if last_cycle_at else None
        ),
        "now": now.isoformat(),
    }
```

The frontend renders idle state as `Idle · last cycle
${getRelativeTime(last_cycle_at)}` using the helper from
`frontend/lib/utils.ts` — the same one every problem card uses today
(`app/page.tsx:178, :270`).

## 7. Risks and trade-offs

### Risk 1 — DB load from per-connection polling

**Cost.** Every connected client triggers two queries every 2 s: the
`list_being_researched` filter and `MAX(research_cycles.created_at)`.

**Mitigation.**

1. The new partial index `ix_problems_research_started_at` keeps the
   filter at O(active_count) instead of seq-scan.
2. Cache `last_cycle_at` for 10 s in-process via `(value,
   monotonic_ts)`. The MAX query then runs ~one round trip per worker
   per 10 s regardless of client count.
3. If ever needed, promote to the centralised poller (see §1).

**Why this is acceptable today.** Even at 100 concurrent SSE clients
per worker, 100 qps to a primary-key partial-index lookup is in the
noise floor of Railway Postgres.

### Risk 2 — Stale `research_started_at` masquerading as live

The agent calls `set_research_status(pid, False)` in a `finally` block
(`research_loop.py:191-192, :292-293`). If the process dies hard
(SIGKILL, OOM, Railway redeploy), the row stays with a stale
`research_started_at`. The 360-s window in `_is_being_researched`
silently expires those, and the SSE handler inherits this for free —
**but** no `research_ended` event is ever emitted because the
server-side state goes from "still active" straight to "no longer
active" without an intermediate state transition the diff loop can
see.

**Concrete failure.** A client that connected at t=10 s after a stale
row sees the stale problem in `snapshot`, never sees `research_ended`,
watches a 350-second-long fake-Researching pulse, then sees the
problem silently disappear in the next snapshot diff.

**Mitigation.** The diff loop's `last_active.keys() -
current_active.keys()` set-difference fires a clean `research_ended`
when timeout expiry causes the problem to drop out of the active set.
The frontend transition logic is unchanged. This is documented in the
`Stale research_started_at is treated as idle` scenario in
`bdd-specs.md`.

**Optional follow-up** (not required for v1): a periodic sweeper on
the API side that explicitly NULLs `research_started_at` for rows
older than 360 s, so the timeout-vs-explicit distinction disappears.
One cron-style task in `_lifespan`. Defer until evidence of real-world
confusion.

### Risk 3 — Multi-worker fan-out timing skew

When N > 1 workers are deployed, each polls independently. A client on
worker A might see `research_started` 1.7 s before a client on worker B.

**Mitigation.** Acceptable. The banner is at-a-glance UX, not a
transactional log. Skew is bounded by `POLL_INTERVAL_SECONDS = 2`.
Document `POLL_INTERVAL_SECONDS` in `core/config.py` so it can be
tuned without redeploying.

### Risk 4 — EventSource not reaching the API in some networks

Some corporate proxies, mobile carriers, and old browsers buffer or
block SSE. The hook handles this by falling back to REST polling after
three errors (§3). Trade-off: a minority of users see 10-second-stale
data instead of 2-second-stale.

### Risk 5 — Long descriptions

`Problem.description` has no DB-level length limit (`Text`). The
banner shows it inline. **Mitigation.** Server-side `description[:300]`
cap in the snapshot payload (already in the example service method
above) plus frontend `line-clamp-1`. Same dual-defense the search
endpoint uses (`presentation/api/routes/search.py:55` —
`item["description"][:200]`).

## 8. Out-of-scope / explicit non-goals

- **No write paths.** The banner never calls `remember`, `report`,
  or `verify`. Read-only by construction (matches the
  `project_web_public_only.md` memory).
- **No per-problem subscription.** All clients see the same global
  stream. Per-problem live updates on `/memories/[id]` would be a
  second endpoint, not a fork of this one.
- **No replay across reconnects.** Discussed in §3.
- **No WebSocket.** SSE is one-way and that suffices.
- **No `is_being_researched` boolean on the snapshot.** The banner
  renders directly from `len(active)`; an explicit boolean would be
  redundant.

## 9. Summary diff — net-new code

Approximate line counts for net-new production code:

- repo Protocol additions: ~10 LOC
- repo implementations (sqlalchemy + in-memory): ~40 LOC
- service method + constant promotion: ~25 LOC
- Pydantic schemas: ~15 LOC
- REST + SSE route handlers: ~120 LOC
- `core/sse_concurrency.py`: ~40 LOC
- migration: ~15 LOC
- `useLiveResearch` hook: ~60 LOC
- `<LiveResearchBanner />` component: ~120 LOC
- API helper: ~10 LOC
- types: ~15 LOC
- `page.tsx` insertion: ~3 LOC
- BDD feature file: see `bdd-specs.md`
- backend unit tests: ~150 LOC
- frontend component test: ~80 LOC

Total: ~700-800 LOC across production + tests. Everything else is
pure reuse.
