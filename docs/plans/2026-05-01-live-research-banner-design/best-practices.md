# Live Research Banner — Best Practices

Cross-cutting concerns: security, performance, code quality, common
pitfalls, and the testing strategy. Anchored against verified facts in
the working tree (CLAUDE.md, .impeccable.md, the existing rate-limit
primitives, the existing CSS tokens, and the per-connection async
poll model recorded in `architecture.md §1`).

## B1. Security

The banner is intentionally public, so the security posture relies on
careful scoping and concurrency limits rather than authentication.
Treat both endpoints exactly like `/v1/search`: anonymous reads are
allowed but bounded, and only already-public problem fields cross the
wire.

- **No auth on either endpoint.** Mirrors the public-read posture in
  `docs/mcp-setup.md` and the contract enforced for `/v1/search` and
  MCP `recall`. Native `EventSource` cannot send custom headers
  anyway.
- **REST endpoint** reuses `@limiter.limit(dynamic_search_limit)`
  from `backend/core/rate_limit.py`: 30/min anonymous (by IP), 300/min
  authenticated (by `agent_id`). No new tier.
- **SSE endpoint** uses a dedicated per-connection concurrency cap in
  the new `backend/core/sse_concurrency.py`:
  - **5** concurrent connections per anonymous IP — enough for two
    browser tabs plus a tunnelled mobile session, well below typical
    proxy fan-out thresholds.
  - **20** per authenticated agent.
  - **200** total per worker (return `503 too_many_streams` past
    that).
  - **15-minute** hard server-side timeout. `EventSource` reconnects
    transparently. Bounds memory if a client process dies without
    closing TCP.
- **Strict event payload allowlist:** `problem_id`, `description`
  (capped at 300 chars), `solution_count`, `best_confidence`,
  `research_started_at`, `elapsed_seconds`, `now`, `last_cycle_at`,
  `active_count`. Never include reporter agent ids, API keys, email
  addresses, or solution markdown bodies.
- **Heartbeat** uses a comment line `:heartbeat <iso-now>\n\n` every
  25 s. Comment lines do not trigger `onmessage`, so no UI re-renders
  and no information leakage. The 25 s cadence sits under the 30 s
  default timeouts of Cloudflare, ALB, and Railway's edge.
- **CORS**: explicitly echo the configured `CORS_ALLOW_ORIGINS` value;
  never return `*`. EventSource ignores cookies on cross-origin
  requests by default, but a wildcard origin still leaks the surface
  to any embedder.

## B2. Performance

The performance story is built on the per-connection 2-second poll
chosen in `architecture.md §1`. The numbers are deliberately
conservative because the project's current scale is single-digit
concurrent viewers.

- **Idle DB load** (no clients connected): zero. The handler only
  runs when a client is connected.
- **DB load per connection per tick**: two queries.
  1. `SELECT … FROM problems WHERE research_started_at IS NOT NULL
     AND research_started_at > now() - interval '360 seconds'`,
     covered by the new partial index
     `ix_problems_research_started_at`. Sub-millisecond.
  2. `SELECT MAX(created_at) FROM research_cycles`, cached
     per-worker for 10 s in a `(value, monotonic_ts)` tuple. ~one
     round trip per worker per 10 s regardless of client count.
- **Browser EventSource limits**: 6 per origin in HTTP/1.1,
  effectively unlimited in HTTP/2. Railway's edge is HTTP/2, so the
  practical limit is the per-IP server cap, not the browser. Operator
  runbook should note this — and the homepage UI never opens more
  than one SSE per origin per tab.
- **Banner DOM cost**: the surface uses `Card`-shaped chrome but
  applies `content-visibility: auto` on the wrapper, so when scrolled
  offscreen the banner stops contributing to layout and paint costs.
  Per `.impeccable.md`'s performance guidance.
- **Backpressure**: FastAPI's `StreamingResponse` buffers naturally;
  the producer's `asyncio.sleep(2)` paces emission. No explicit
  queues to drain.
- **Promotion path** (architecture.md §1): if connections per worker
  exceed ~200 or research toggles exceed ~10 Hz, extract the diff
  loop into an `asyncio.Task` started in `_lifespan` that fans out
  via `asyncio.Queue`. The SSE handler signature does not change.
- **Frontend re-renders**: the banner is the only part of `page.tsx`
  that subscribes to live state. Wrap the content in `React.memo`
  keyed on `snapshot.active[0].problem_id` plus
  `snapshot.last_cycle_at`, so the unrelated tabs do not re-render
  when the banner ticks.

## B3. Code quality

The banner must look like it was always part of the homepage — not
an afterthought. Reuse the existing tokens, the existing `Researching`
badge, and the homepage's existing `useEffect` patterns.

- **Reuse, do not invent.** Use `--research-glow-strong`,
  `--research-glow-soft`, `--research-dot`, `.research-active`,
  `.researching-dot`, `.researching-ping`, the `research-pulse`
  keyframes, and the `Researching` badge variant. Do **not** add new
  tokens. They already match the coral accent prescribed in
  `.impeccable.md`.
- **Match React patterns** already in `frontend/app/page.tsx`:
  - Dynamic-import `TitleMarkdown` exactly the way the file does at
    lines 81-94 (with a `LoadingSpinner` fallback).
  - `useEffect` cleanup that closes the `EventSource` and aborts any
    pending REST `fetch` via an `AbortController`. React StrictMode
    double-mounts in dev; verify the connection counter on the
    server stays at 1 for a single dev tab.
  - Use `getRelativeTime` from `frontend/lib/utils.ts`. It is
    `Intl.RelativeTimeFormat`-based and is already used by every
    problem card.
- **Idle copy**: `"Idle · last cycle Xm ago"` and
  `"Idle · awaiting first cycle"`. Calm, lowercase-friendly, no
  emojis, no exclamation marks. This is the workshop voice from
  `.impeccable.md`.
- **BDD-driven TDD**: per CLAUDE.md, the `.feature` file lands first,
  the failing pytest/vitest second, the implementation third.
- **Layer order**: domain Protocol additions →
  infrastructure repo impls → service method → presentation route
  → frontend hook → frontend component → wire-in. See the suggested
  order in `_index.md §Detailed Design`.
- **Format**: Ruff for Python (line length 88, double quotes), Biome
  for TypeScript (2-space indent, double quotes, always semicolons).
  Run `uv run ruff format . && uv run ruff check --fix .` before
  commit; run `cd frontend && pnpm lint` before merge.
- **No new dependencies**:
  - Backend: do not add `sse_starlette`. Use FastAPI's built-in
    `StreamingResponse(media_type="text/event-stream")` with an async
    generator.
  - Frontend: do not add `swr`, `@tanstack/react-query`, or
    `react-use`. Use the platform `EventSource` API directly inside
    `useLiveResearch`.

## B4. Common pitfalls

Live UIs accumulate quiet bugs. The list below names the ones most
likely to bite an agentbook implementation given the current
architecture.

- **Client-side reconnect race.** `EventSource` auto-reconnects on
  close, but our hook also has its own three-error fallback timer
  and a 60 s "try to re-open SSE while in REST mode" timer. Make sure
  cancelling a `setInterval`/`setTimeout` in the cleanup actually
  runs before a stale callback fires; otherwise dev-mode StrictMode
  double-mount produces ghost connections.
- **Heartbeat must not be a `data:` line.** Use a comment line
  (`:heartbeat …\n\n`) so the browser does not invoke `onmessage`
  every 25 s. A bug here causes the React banner to re-render on
  every heartbeat and pollutes a11y announcements.
- **Stale `research_started_at` after agent crash** is the entire
  reason for the 360 s freshness window. Never rely on the agent to
  clear the flag on shutdown — `_is_being_researched` is the only
  correct read path.
- **`aria-live` overuse** can spam screen readers when the agent
  flicks between problems quickly. Debounce announcements by 1 s and
  collapse repeated identical announcements into one. Keep the visual
  update immediate; only the assistive-tech announcement is
  debounced.
- **Multi-worker drift.** With horizontal scaling (`mcp_stateless=
  True`), two workers will diverge on which problem is "most recent"
  if the snapshot is computed per-worker without a tie-breaker. The
  service method orders the active list by
  `research_started_at DESC` to keep the tie-break deterministic
  across workers.
- **`description` length explosion.** `Problem.description` has no
  DB-level length limit. The service method caps to 300 chars in the
  payload; the frontend uses `line-clamp-1`. Both layers protect.
- **`EventSource` ignores `withCredentials` cookies cross-origin** —
  fine here because the endpoint is anonymous, but worth documenting
  so a future "make this authenticated" patch does not silently
  break.
- **`EventSource` is not natively in jsdom.** vitest tests must
  install or write a tiny stub class with `addEventListener` and a
  manual `dispatch` method. See the test plan below.

## B5. Testing strategy

Mirrors the rest of the repo: many fast unit tests, a thin smoke ring
around the wire format, vitest on the React surface, and no
Playwright (none is configured).

### Unit (backend, `backend/tests/unit/`)

Cover against the in-memory service with the autouse fixtures in
`backend/tests/conftest.py`:

- `service.get_live_research_snapshot` empty state.
- 360 s window edge cases: 359 s = active, 361 s = idle.
- Multi-active deterministic ordering by
  `research_started_at DESC`.
- `last_cycle_at = None` when `research_cycles` is empty.
- `description` truncation at 300 chars.
- Event payload allowlist (assert no PII keys leak).
- New repo methods: `list_being_researched`,
  `get_latest_cycle_at` against in-memory.

### Integration (backend, `backend/tests/integration/`, `@pytest.mark.smoke`)

- Drive the FastAPI app with `httpx.AsyncClient`. Assert the SSE
  handshake: 200, `Content-Type: text/event-stream`, an initial
  `event: snapshot` frame, then drive a state change via
  `service.set_research_status` and assert the next chunk contains
  `event: research_started`.
- Heartbeat scenario: hold a connection for >25 s, assert exactly
  one `:heartbeat` line appears.
- Hard-timeout scenario: hold a connection past 15 min (use a
  patched constant) and assert clean close + reconnect-friendly
  state.
- Per-IP cap scenario: open 5 connections from the same IP, the 6th
  returns `429`.
- New repo methods against real Postgres in
  `backend/tests/integration/test_sqlalchemy_repos.py`.

### Frontend (`frontend/tests/`, vitest + jsdom)

- Mock `EventSource` (jsdom does not ship it).
- Banner renders the active problem after a `research_started`
  event.
- Banner switches to `"Idle · last cycle Xm ago"` after a
  `research_ended` event.
- Title link navigates to `/memories/{id}`.
- `prefers-reduced-motion: reduce` snapshot test asserts no
  inline animation styles override the static fallback.
- Three consecutive `onerror` events trigger
  `fetchLiveResearchSnapshot` polling and surface the
  `(reconnecting)` hint.
- `aria-live="polite"` announcement debounce: simulate two
  transitions within 500 ms and assert only one announcement was
  enqueued.

### End-to-end

Skip. Playwright is not in the dependency tree per CLAUDE.md, and
adding it for a single banner is not proportionate.

### Performance (`backend/tests/performance/`, `@pytest.mark.perf`, `RUN_PERF_TESTS=1`)

- Open 100 concurrent SSE connections to a single worker. Assert:
  - zero connection refusals below the per-IP cap (use distinct
    fake IPs);
  - at most one `MAX(research_cycles.created_at)` query per worker
    per 10 s (instrument with the existing repo counter);
  - steady memory across a 60-second window.
- Use the harness already present in `backend/tests/performance/`.
