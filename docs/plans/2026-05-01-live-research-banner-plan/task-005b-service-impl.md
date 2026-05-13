# Task 005b: service.get_live_research_snapshot() — Green

**depends-on**: 005a

## Description

Implement `AgentbookService.get_live_research_snapshot()` using the new repo methods from task 004b. Server-side cap on `description` at 300 chars, deterministic ordering, ISO 8601 serialisation. The method composes existing primitives and exposes a strict allowlist payload.

## Execution Context

**Task Number**: 005b of 20
**Phase**: Application Service — Green
**Prerequisites**: Task 005a (failing tests).

## BDD Scenario

(Same scenarios as 005a — this task makes them PASS.)

```gherkin
Scenario: Stale research_started_at is treated as idle (agent crash protection)
  Given problem "P-1" has research_started_at set 7 minutes ago
  When the snapshot is computed
  Then "P-1" is excluded from the snapshot's active list

Scenario: Event payload exposes only public fields
  When the snapshot is computed
  Then the JSON payload contains exactly the allowed keys
  And no PII or agent identifiers leak
```

## Files to Modify/Create

- Modify: `backend/application/service.py`

## Steps

### Step 1: Add the service method

In `backend/application/service.py`, add (signatures and shape only — body is implementation work):

```python
def get_live_research_snapshot(self) -> dict:
    """Returns the live-research snapshot for the dashboard banner.

    Shape:
        {
            "active": [
                {
                    "problem_id": str,
                    "description": str,           # truncated to 300 chars
                    "solution_count": int,
                    "best_confidence": float,
                    "research_started_at": str,   # ISO 8601 UTC
                    "elapsed_seconds": int,
                },
                ...                                # ordered by research_started_at DESC
            ],
            "last_cycle_at": str | None,           # ISO 8601 UTC or None
            "now": str,                            # ISO 8601 UTC
        }

    The active list is filtered through the existing 360s freshness window
    (RESEARCH_TIMEOUT_SECONDS). last_cycle_at is the global
    MAX(research_cycles.created_at). All timestamps are ISO 8601 strings.
    """
    ...
```

Implementation must:

- Call `self._problems.list_being_researched(timeout_seconds=RESEARCH_TIMEOUT_SECONDS)`.
- Call `self._research_cycles.get_latest_cycle_at()` (guard with `if self._research_cycles is not None`).
- Truncate each `Problem.description` to 300 chars before serialisation.
- Compute `elapsed_seconds = int((now - p.research_started_at).total_seconds())` per active item.
- Order matches the repo's order (already DESC).
- Use `utc_now()` from existing helpers; do not import a fresh `datetime.utcnow`.
- Never include `author_id`, `reporter_id`, agent emails, or solution markdown bodies in the payload.

### Step 2: Run tests to confirm Green
```bash
uv run pytest backend/tests/unit/test_service_live_research.py -x
```

All 10 tests must PASS.

### Step 3: Re-run dependent existing tests
```bash
uv run pytest backend/tests/unit -k "service" -x
```

Existing service tests must still pass.

### Step 4: Format and lint
```bash
uv run ruff format backend/application/service.py
uv run ruff check --fix backend/application/service.py
```

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_service_live_research.py -x
uv run pytest backend/tests/unit -k "service" -x
uv run ruff check backend/application/service.py
```

## Success Criteria

- 10/10 tests in `test_service_live_research.py` pass.
- All existing service tests still pass.
- No new dependency added; method composes existing primitives only.
- Method docstring documents the shape verbatim.
- Ruff format + check both pass.
