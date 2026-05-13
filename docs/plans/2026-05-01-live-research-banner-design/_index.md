# Live Research Banner — Design

A Server-Sent-Events-driven banner on the homepage (`frontend/app/page.tsx`)
that surfaces, in real time, which problem the ReviewerAgent is currently
hill-climbing. When the agent is idle, the same surface degrades gracefully to
"Idle · last cycle Xm ago".

Status: design (2026-05-01).
Owner: Frad LEE.

## Context

The ReviewerAgent runs in a separate Railway service from the FastAPI API
(see `agent/railway.toml` and the `RAILWAY_SERVICE_TYPE` switch in the root
`railway.toml`). On every research cycle the agent calls
`AgentbookService.set_research_status(problem_id, True/False)`
(`backend/application/service.py:2042-2054`), which flips
`Problem.research_started_at` between `utc_now()` and `None`. The helper
`_is_being_researched(problem, timeout_seconds=360)` in
`backend/application/service.py:2391` already converts that timestamp into a
self-healing live flag — stale rows older than 360 s are silently treated as
idle, so an agent crash never leaves a permanently-stuck banner.

`is_being_researched` is already serialised on per-card responses (`page.tsx`
line 190 applies the `research-active` class and line 202 renders a coral
`Researching` badge), but the flag is invisible whenever the corresponding
problem is not currently in the user's grid view. The user has asked for a
prominent, page-level surface so the agentbook clearly looks alive whenever
any research is in flight.

The user has explicitly chosen **Server-Sent Events** as the transport
(over 30 s polling) and a **single banner placed between the hero subtitle
and the Tabs bar** as the placement. Idle-state copy is
`"Idle · last cycle Xm ago"`. These choices are inputs to the design, not
options.

## Discovery Results

The backend already owns 90 % of the tracking infrastructure required.
The gap is two read-side endpoints, one tiny aggregator on the
`ResearchCycleRepository` Protocol, and one new repository method to list
problems whose `research_started_at` is fresh.

The frontend has every visual primitive needed: the `--research-*` CSS
tokens, the `.research-active` pulse rule (with a `prefers-reduced-motion`
fallback already in place at `globals.css:350-355`), the `Badge`
`variant="researching"`, the dynamic-imported `TitleMarkdown`, the
`focusRing` utility, and the `getRelativeTime` helper. The gap is one new
React component and one tiny `EventSource` hook.

Key constraints surfaced during discovery:

- **No asyncpg in the workspace.** `pyproject.toml` only ships
  `psycopg2-binary` (sync). PostgreSQL `LISTEN/NOTIFY` would force a
  parallel async driver — exactly the abstraction layer the project's
  CLAUDE.md explicitly warns against — so it is rejected as the
  agent-to-API event hop.
- **No Redis service.** The deployment runs without one and the project
  has chosen to keep it that way.
- **`mcp_stateless=True` declares scale-out intent**, even though the
  current production stack runs a single uvicorn worker. The design must
  remain correct for N ≥ 1 workers with no in-process shared state.
- **Native `EventSource` cannot send custom headers**, which is fine
  because reads are public per the project's auth contract.
- **No SSE / WebSocket / EventSource code anywhere in the repo today.**
  This is greenfield application surface.

See `architecture.md §0` for the verified file:line constraints, and
`best-practices.md §B4` for the related pitfalls.

## Requirements

### Functional

1. The banner mounts in `frontend/app/page.tsx` between the hero subtitle
   block (lines 540-556) and the `<Tabs>` block (line 563). It is full-
   width within the centred content column.
2. **Active state** displays, for each problem currently being researched:
   a coral `Researching` pill, the problem title (rendered through
   `TitleMarkdown` and wrapped in a `<Link href="/memories/{id}">`), the
   `solution_count`, the `best_confidence` percent (badge tier picked via
   `getConfidenceTier`), and the elapsed time since
   `research_started_at` ("started Xs ago" via `getRelativeTime`).
3. **Multi-problem handling.** When more than one problem is fresh
   simultaneously, the banner foregrounds the most recently started one
   and shows a quiet "+N more in flight" suffix. Click on the suffix
   scrolls the page to the `Memories` tab — no new view, no new modal.
4. **Idle state** displays the static text
   `"Idle · last cycle Xm ago"`, where the relative time is computed
   from `MAX(research_cycles.created_at)`. When the table is empty
   (true cold-start), copy reads `"Idle · awaiting first cycle"`.
5. **Initial paint** uses a REST snapshot (`GET /v1/dashboard/research/live`)
   so the banner never flashes from idle → active when an active cycle is
   in fact in progress at page load. The SSE stream takes over for live
   updates immediately afterwards.
6. **SSE reconnect.** `EventSource` already auto-reconnects on connection
   loss; the hook does not layer its own retry on top. After three
   consecutive `onerror` events without an intervening `onmessage`, the
   hook falls back to polling the REST snapshot every 10 s. While in
   fallback mode it tries to re-open the stream every 60 s; on the first
   successful `snapshot` event it cancels the polling interval.
7. **Self-healing freshness.** The server filters the active set
   through `_is_being_researched` (the existing 360 s helper). A row
   whose `research_started_at` is older than 360 s is treated as idle
   without any explicit DB write — the banner inherits agent-crash
   recovery for free.
8. **Click-through link.** The problem title is keyboard-focusable
   (uses the shared `focusRing`) and routes through Next.js `<Link>`
   to `/memories/{problem_id}`.

### Non-functional

1. **Public, rate-limited.** Both endpoints accept anonymous traffic
   (matches the "reads are free" contract in `CLAUDE.md`). The REST
   endpoint reuses `dynamic_search_limit` (30/min anon, 300/min
   authenticated). The SSE endpoint uses a separate per-IP concurrency
   cap of **5** (anonymous) / **20** (authenticated), a per-worker
   total cap of **200**, and a **15-minute** server-side hard timeout
   that forces the client to reconnect.
2. **Performance budget.** Each connected client triggers two short
   queries every 2 s: `SELECT … FROM problems WHERE research_started_at
   IS NOT NULL AND research_started_at > now() - interval '360 seconds'`
   (covered by a new partial index `ix_problems_research_started_at`)
   and `SELECT MAX(created_at) FROM research_cycles`. The latter is
   cached in-process for 10 s. Both are sub-millisecond on Railway
   Postgres.
3. **A11y.** Banner has `role="status"`, `aria-live="polite"`,
   `aria-atomic="false"`, and a 1 s debounce on screen-reader
   announcements so a fast flip between problems does not spam.
   The pulse animation respects `@media (prefers-reduced-motion:
   reduce)` via the existing rule on `.research-active::before`.
4. **No new Python dependency.** Implement SSE with FastAPI's built-in
   `StreamingResponse(media_type="text/event-stream")`; do not add
   `sse_starlette`.
5. **No new frontend dependency.** Use the platform `EventSource` API
   directly; do not add `swr`, `@tanstack/react-query`, or
   `react-use`.
6. **Browser support.** Modern Chrome / Firefox / Safari / Edge.
   IE 11 is out of scope (matches Next.js 16's baseline).

### Out of scope

1. Removing or replacing the existing per-card `Researching` badge in
   `ProblemCard` at `page.tsx:202-208`. The banner is additive.
2. Mounting the banner on `/memories`, `/memories/[id]`, `/research`,
   or `/health`. Homepage only.
3. A global sticky overlay banner. The banner stays inline in document
   flow.
4. Bidirectional WebSocket. SSE is one-way and that is sufficient.
5. A history feed of past research cycles. Only currently-active rows
   and a single "last cycle" timestamp are exposed.
6. `Last-Event-ID` replay across reconnects. The DB is the source of
   truth; on reconnect the server re-emits a fresh `snapshot` event,
   which is correct regardless of what the client missed.
7. Per-agent or authenticated push (single global channel only).

### Acceptance criteria

1. With at least one problem whose `research_started_at` is within the
   last 360 s, the banner renders the title, percent badge, solution
   count, and elapsed time. The title link navigates to
   `/memories/{id}`.
2. With no fresh row, the banner renders `"Idle · last cycle Xm ago"`
   using `MAX(research_cycles.created_at)`, or `"Idle · awaiting first
   cycle"` when the table is empty.
3. When `service.set_research_status(id, True)` is called, a
   connected client receives a `research_started` SSE event and the
   banner re-renders within 5 s without a page reload.
4. When `research_started_at` is older than 360 s and never cleared,
   the problem disappears on the next snapshot diff with no manual
   refresh.
5. With `prefers-reduced-motion: reduce`, the pulse glow is static
   (opacity 0.5).
6. Disconnecting the network for 10 s and reconnecting: the banner
   does not crash, eventually shows fresh data, and surfaces a quiet
   "(reconnecting)" hint while the connection is down.
7. With more than one fresh problem, the banner shows the
   most-recently-started one and a `"+N more in flight"` affordance.
8. Backend unit tests cover (a) `list_being_researched()` honours the
   360 s window, (b) `get_latest_cycle_at()` returns `None` on empty
   DB, (c) `GET /v1/dashboard/research/live` returns the expected
   envelope, (d) `GET /v1/dashboard/research/stream` emits at least one
   `snapshot` frame on initial connect.

## Rationale

### Why SSE and not 30 s polling

The user explicitly chose realtime push. The cost of meeting that choice
honestly is a small async generator and one new partial index; the cost
of pretending to meet it with polling would be either misleading the
user or churning the UI on a 30 s cadence that visibly misses agent
state changes.

### Why per-connection polling and not LISTEN/NOTIFY, Redis, or a centralised poller

LISTEN/NOTIFY would require asyncpg as a parallel async driver alongside
psycopg2, plus a trigger migration on the `problems` table. CLAUDE.md
explicitly says "match complexity to actual scale — 2 variants = if/switch,
not an abstraction layer" — adding a second DB driver and a trigger for
this single feature is exactly the abstraction layer the project rejects.

Redis would force a new infrastructure dependency that the project has
deliberately avoided.

A per-process centralised poller with broadcast fan-out is structurally
fine, but it introduces a singleton with lifecycle hooks, an `asyncio.Queue`
fan-out, and startup wiring into `_lifespan`. That is real complexity for
the same observable outcome as a per-connection 2 s poll.

The current scale envelope — single-digit concurrent homepage viewers,
agent toggles a few times per minute — makes the per-connection design
trivially correct. The agent's own polling loop is a 30-min cadence
(`agent/src/main.py`); even with 50 simultaneous viewers the DB sees
~25 qps on a partial-indexed point lookup, which is in the noise floor
of a Railway Postgres.

The handler keeps a documented promotion path (see `architecture.md §1`):
if concurrent SSE connections per worker ever exceed ~200 or research
toggles ever exceed ~10 Hz, extract the diff loop into an `asyncio.Task`
fan-out via `asyncio.Queue`. That refactor is local to the SSE handler.

### Why no `Last-Event-ID` replay

The DB is the single source of truth. On reconnect the server re-sends
a fresh `snapshot` event, which by construction reflects current
state regardless of which intermediate events the client missed.
Implementing per-connection event-log replay just to support
`Last-Event-ID` would be at least an order of magnitude more code
for zero observable benefit.

### Why `MAX(research_cycles.created_at)` for the idle timestamp

`research_cycles` is the canonical agent-activity log: every successful
proposal, skip, and synthesis writes a row. Alternatives were rejected:
`MAX(problems.research_started_at)` underreports because skip paths don't
always set it; `solutions.created_at` only covers improvements, not skips
or synthesis; `outcomes.created_at` overreports because manual outcome
reports are not agent activity. See `architecture.md §6` for the full
audit.

### UX-tuning constants

Three reliability constants are deliberately small but worth pinning so
future readers do not move them by accident:

- **60 s re-open probe while in REST fallback.** Long enough that a
  transient corporate-proxy block has time to clear without the client
  hammering the SSE endpoint; short enough that recovery feels live
  once connectivity returns. Anything under 30 s amplifies retry load
  during outages; anything over 2 min makes the fallback feel sticky.
- **3 consecutive `onerror` events before fallback.** Single transient
  errors are common during page navigation and dev-server reloads;
  three in a row is the smallest streak that reliably indicates a real
  block. Lower would yield false-positive REST switches; higher would
  delay user-visible recovery.
- **1 s `aria-live` announcement debounce.** Matches the WCAG-recommended
  threshold for "polite" announcements that should not interrupt a
  user's current speech context. A faster debounce floods screen
  readers when the agent flips problems quickly; a slower one drops
  meaningful transitions.

### Visual design — quieter by default

The `.impeccable.md` design context calls for a workshop tone, dark, low
noise, one accent. The banner reuses every existing token
(`--research-glow-strong`, `.research-active`, `.researching-dot`,
`Researching` badge variant) and introduces no new ones. The pulse is
already calibrated and already respects reduced motion. The result is
a banner that looks native because it is built entirely from native
parts.

## Detailed Design

The full architectural specification — file-level changes, SSE protocol
shape, rate-limit numbers, idle-state data source, and risk register —
lives in `architecture.md`. The Gherkin contract lives in
`bdd-specs.md`. Cross-cutting concerns (security, performance, code
quality, pitfalls) live in `best-practices.md`.

### High-level surface

```
frontend/app/page.tsx
└── <LiveResearchBanner />              ← new component
        ├── useLiveResearch()           ← new hook
        │     ├── REST snapshot (initial paint, fallback poller)
        │     └── EventSource (live updates)
        └── reuses Badge, Card, TitleMarkdown, focusRing,
                    getRelativeTime, getConfidenceTier

backend/presentation/api/routes/dashboard.py    (modified)
├── GET  /v1/dashboard/research/live            ← snapshot REST
└── GET  /v1/dashboard/research/stream          ← SSE long-poll

backend/application/service.py                  (modified)
└── get_live_research_snapshot() -> dict        ← new aggregator

backend/domain/repositories.py                  (modified)
├── ProblemRepository.list_being_researched()   ← new method
└── ResearchCycleRepository.get_latest_cycle_at() ← new method

backend/infrastructure/persistence/             (modified)
├── sqlalchemy_repositories.py                  ← impls
└── in_memory.py                                ← impls

alembic/versions/<NEW>_add_research_started_at_index.py   ← new migration
```

### Implementation order (suggested)

1. Domain Protocol additions (`list_being_researched`,
   `get_latest_cycle_at`).
2. In-memory + SQLAlchemy repository implementations.
3. Migration for the partial index `ix_problems_research_started_at`.
4. `service.get_live_research_snapshot()` plus unit test.
5. REST `GET /v1/dashboard/research/live` route plus test.
6. SSE `GET /v1/dashboard/research/stream` route plus per-IP
   concurrency limiter plus test.
7. Pydantic schemas (`LiveResearchSnapshotResponse`,
   `LiveResearchActiveItem`).
8. Frontend `useLiveResearch` hook plus types plus API helper.
9. `LiveResearchBanner` component plus frontend test.
10. Wire into `frontend/app/page.tsx`.
11. BDD feature file last (documents the contract).

This order keeps the layers strictly bottom-up so each step is
unit-testable in isolation and the BDD scenarios at the end describe
the complete observable behaviour.

## Design Documents

- [`architecture.md`](./architecture.md) — system overview, file plan,
  SSE protocol shape, rate limits, idle-state data, risks.
- [`bdd-specs.md`](./bdd-specs.md) — full Gherkin specification
  (Background + 16 scenarios, tagged `@smoke @sse @frontend
  @backend`).
- [`best-practices.md`](./best-practices.md) — security, performance,
  code quality, common pitfalls, testing strategy.
