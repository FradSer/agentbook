# Task 005a: service.get_live_research_snapshot() — Red

**depends-on**: 004b

## Description

Add failing unit tests for the new `AgentbookService.get_live_research_snapshot()` aggregator. Cover: empty state, single active problem, multi-active deterministic ordering, stale row exclusion (360 s window), idle-state `last_cycle_at`, payload allowlist (no PII), and 300-character description truncation. Tests must FAIL until task 005b lands.

## Execution Context

**Task Number**: 005a of 20
**Phase**: Application Service — Red
**Prerequisites**: Task 004b (repo methods are real, so the service can rely on them).

## BDD Scenario

```gherkin
Scenario: Stale research_started_at is treated as idle (agent crash protection)
  Given problem "P-1" has research_started_at set 7 minutes ago
  And the agent process crashed without clearing the flag
  When a client subscribes to the SSE stream
  Then "P-1" is excluded from the snapshot's active list
  And the banner renders "Idle - last cycle 7m ago"

Scenario: Event payload exposes only public fields
  When the server emits a "research_started" event
  Then the JSON payload contains keys "problem_id", "description",
    "solution_count", "best_confidence", "research_started_at", "now"
  And the payload contains no agent identifiers
  And the payload contains no API keys
  And the payload contains no email addresses
  And the payload contains no solution markdown bodies

Scenario: Long problem descriptions are truncated client-side
  Given the snapshot payload's "description" is at the 300-character server cap
  When the banner renders that description
  Then the visible text uses Tailwind class "line-clamp-1"
  And the underlying anchor's accessible name is the full description
```

(The 300-char server cap is asserted server-side in this task; the
`line-clamp-1` half belongs to task 012a.)

**Spec Source**: `../2026-05-01-live-research-banner-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_service_live_research.py`

## Steps

### Step 1: Write failing tests (Red)

Required test contracts (signatures only — no implementation in this plan):

```python
def test_snapshot_empty_state_returns_empty_active_and_null_last_cycle():
    """No problems, no cycles → {"active": [], "last_cycle_at": None, "now": <iso>}."""
    ...

def test_snapshot_includes_single_active_problem():
    """One fresh problem → active list has one item with all required keys."""
    ...

def test_snapshot_orders_active_by_research_started_at_desc():
    """Three fresh problems → list ordered most-recent-first (deterministic across workers)."""
    ...

def test_snapshot_excludes_stale_row_at_361_seconds():
    """research_started_at 361s ago → excluded (window edge)."""
    ...

def test_snapshot_includes_row_at_359_seconds():
    """research_started_at 359s ago → included (window edge)."""
    ...

def test_snapshot_returns_global_max_last_cycle_at():
    """With cycles across multiple problems, returns MAX(created_at) globally."""
    ...

def test_snapshot_active_item_payload_allowlist():
    """Each active item exposes EXACTLY: problem_id, description, solution_count,
    best_confidence, research_started_at, elapsed_seconds. No agent_id, no
    reporter, no email, no markdown body."""
    ...

def test_snapshot_truncates_description_to_300_chars():
    """A 500-char description is truncated to 300 chars in the payload."""
    ...

def test_snapshot_research_started_at_serialised_as_iso8601():
    """research_started_at and now are ISO 8601 strings, not datetime objects."""
    ...

def test_snapshot_uses_research_timeout_seconds_constant():
    """Window respects RESEARCH_TIMEOUT_SECONDS imported from service module."""
    ...
```

Use the autouse `database_url=None` fixture from `backend/tests/conftest.py` so this is unit-scoped (in-memory repos).

### Step 2: Confirm Red
```bash
uv run pytest backend/tests/unit/test_service_live_research.py -x
```

Every test must FAIL with `AttributeError: 'AgentbookService' object has no attribute 'get_live_research_snapshot'`.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_service_live_research.py -x
# Expected: 10 FAILED tests, all AttributeError on missing method
```

## Success Criteria

- 10 unit tests added, all FAIL for the intended reason.
- Tests pass `description` strings of varying lengths to verify truncation precisely at 300 chars.
- No production code modified.
- Tests use `freezegun` or the existing time-control fixture for deterministic 359/361 second assertions.
