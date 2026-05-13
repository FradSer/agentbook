# Task 009a: GET /v1/dashboard/research/stream SSE endpoint — Red

**depends-on**: 007b, 008b

## Description

Add failing integration tests for the SSE stream endpoint at `/v1/dashboard/research/stream`. Cover: 200 + `Content-Type: text/event-stream` on connect, initial `event: snapshot` frame, diff loop emitting `research_started` / `research_ended` on state change, `:heartbeat` comment line every 25 s, 15-min hard server-side timeout, per-IP cap enforcement (returns 429 for the 6th connection from same IP), `Last-Event-ID` is NOT honoured (server re-emits fresh snapshot), payload allowlist, structured logging for toggle-rate metric, and CORS allowlist behaviour.

These tests use `httpx.AsyncClient` with `client.stream("GET", url)` to read the chunked response and parse SSE frames.

## Execution Context

**Task Number**: 009a of 20
**Phase**: Presentation — SSE Stream Red
**Prerequisites**: Task 007b (REST endpoint), Task 008b (concurrency limiter).

## BDD Scenario

```gherkin
Scenario: Anonymous client subscribes successfully (public read endpoint)
  Given the request carries no Authorization header
  When the client opens the SSE stream
  Then the server responds with status 200
  And the response Content-Type is "text/event-stream"
  And no API key is required

Scenario: Concurrent SSE connections per anonymous IP are capped at 5
  Given the configured per-IP cap is 5 concurrent SSE connections
  And the same remote IP already holds 5 open SSE connections
  When the same IP opens a 6th SSE connection
  Then the server responds with status 429
  And the response body contains error "rate_limit_exceeded"
  And the existing 5 connections from that IP are not affected

Scenario: Reconnect emits a fresh snapshot instead of replaying missed events
  Given the client has previously received "research_started" for "P-1"
  And the client connection drops
  When the client reconnects to the SSE stream
  Then the server does not honour "Last-Event-ID"
  And the server's first frame is a fresh "snapshot" event
  And the snapshot reflects the current DB state regardless of what was missed

Scenario: Stale row falling out of the active set fires a clean research_ended
  Given the banner has rendered "P-1" from a snapshot whose research_started_at
    was 359 seconds ago
  When 2 seconds elapse and the next server-side poll runs
  Then "P-1" no longer satisfies the freshness window
  And the server emits a "research_ended" event for "P-1"

Scenario: Heartbeat keeps proxies from closing the SSE stream
  Given the SSE connection has been open for 25 seconds with no state change
  When the heartbeat timer fires
  Then the server writes a comment line beginning with ":heartbeat"
  And the line is terminated by a blank line
  And the client's onmessage handler is not invoked

Scenario: Server hard-closes idle streams after 15 minutes
  Given the SSE connection has been open for 15 minutes
  When the hard-timeout deadline elapses
  Then the server closes the response stream cleanly
  And the new connection emits a fresh "snapshot" event as its first frame

Scenario: Active backend caches last_cycle_at for 10 seconds in-process
  Given a single SSE connection is open
  And research_cycles is queried for "MAX(created_at)" on the first poll
  When subsequent polls run within 10 seconds
  Then the worker reuses the cached "last_cycle_at" value
  And no new query is issued for "MAX(research_cycles.created_at)"

Scenario: Toggle-rate metric exposes the centralised-poller promotion threshold
  Given the SSE handler emits a structured log line on each "research_started"
    and "research_ended" event
  When operators query the log stream over a 60-second window
  Then the observed toggle rate (events per second) is computable from the logs
  And exceeding 10 toggles per second is the documented signal to promote
```

(Plus: CORS scenario, payload allowlist scenario.)

**Spec Source**: `../2026-05-01-live-research-banner-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_dashboard_stream_route.py`
- Create: `backend/tests/integration/test_dashboard_stream_smoke.py` (optional integration covering true Postgres + horizontal-scale skew)

## Steps

### Step 1: Write failing tests (Red)

Required test contracts in `test_dashboard_stream_route.py`:

```python
async def test_stream_returns_200_anonymous_with_event_stream_content_type():
    ...

async def test_stream_first_frame_is_snapshot_event():
    """First chunk parses as 'event: snapshot\\n' with valid JSON data."""
    ...

async def test_stream_emits_research_started_when_state_changes():
    """Drive set_research_status(pid, True), assert next frame is research_started."""
    ...

async def test_stream_emits_research_ended_when_problem_clears():
    """Drive set_research_status(pid, False), assert next frame is research_ended."""
    ...

async def test_stream_stale_row_emits_research_ended_via_diff_loop():
    """Freeze time advance past 360s, assert research_ended fires from set diff."""
    ...

async def test_stream_heartbeat_comment_line_after_25s():
    """Use freezegun or asyncio sleep mock; assert ':heartbeat' line appears."""
    ...

async def test_stream_does_not_honour_last_event_id_on_reconnect():
    """Reconnect with header Last-Event-ID: 5, server still sends event id: 0 snapshot."""
    ...

async def test_stream_hard_closes_at_15_minutes():
    """Patch HARD_TIMEOUT_SECONDS=2; assert connection closes cleanly after 2s."""
    ...

async def test_stream_per_ip_cap_returns_429_on_sixth_connection():
    """Open 5 concurrent streams from same client IP, the 6th returns 429
    with body containing 'rate_limit_exceeded'."""
    ...

async def test_stream_payload_allowlist_no_pii_keys():
    """Each yielded JSON has only the allowed keys: problem_id, description,
    solution_count, best_confidence, research_started_at, elapsed_seconds, now,
    last_cycle_at. NO agent_id, NO reporter_id, NO email, NO API keys, NO
    solution markdown bodies."""
    ...

async def test_stream_logs_research_started_and_ended_for_metric_extraction():
    """Each diff event produces a structured log line with 'event=research_started'
    or 'event=research_ended' and the problem_id."""
    ...

async def test_stream_caches_last_cycle_at_for_10_seconds():
    """Observe MAX query count across 5 ticks: ≤ 1 query for the first 10s."""
    ...

async def test_stream_cors_allowlist_echoes_configured_origin():
    """Same as REST CORS test but for the SSE endpoint."""
    ...
```

Use the `httpx.AsyncClient` SSE-parsing pattern (read chunked text, split on `\n\n`, parse `event:` and `data:` lines).

### Step 2: Confirm Red
```bash
uv run pytest backend/tests/unit/test_dashboard_stream_route.py -x
```

All 13 tests must FAIL.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_dashboard_stream_route.py -x
# Expected: 13 FAILED tests
```

## Success Criteria

- 13 unit tests added, all FAIL for the intended reason (route not registered).
- Tests use deterministic time control (freezegun or `asyncio.sleep` mock).
- Tests parse SSE frames with the standard `\n\n` boundary; do not rely on `aiosseclient` or similar.
- Cap test reuses the limiter from task 008b.
- No production code modified.
