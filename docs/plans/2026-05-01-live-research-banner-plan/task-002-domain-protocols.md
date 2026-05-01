# Task 002: Domain Protocol additions and RESEARCH_TIMEOUT_SECONDS constant

**depends-on**: 001

## Description

Add two pure-interface methods to the domain Protocol layer and promote the existing `360` literal in `_is_being_researched()` to a module-level constant. Pure interface work — no implementation bodies. Implementations land in task 004b.

## Execution Context

**Task Number**: 002 of 20
**Phase**: Foundation — Domain
**Prerequisites**: Feature file from task 001 (so later test tasks can reference it).

## BDD Scenario

The two new Protocol methods are exercised by these scenarios:

```gherkin
Scenario: list_being_researched honours the 360s window
  Given problem "A" has research_started_at 359 seconds ago
  And problem "B" has research_started_at 361 seconds ago
  And problem "C" has research_started_at set to NULL
  When list_being_researched is called with timeout_seconds=360
  Then the result includes "A"
  And the result excludes "B"
  And the result excludes "C"

Scenario: get_latest_cycle_at returns None on empty research_cycles
  Given the research_cycles table is empty
  When get_latest_cycle_at is called
  Then the result is None
  And the snapshot's "last_cycle_at" field serialises as null
```

**Spec Source**: `../2026-05-01-live-research-banner-design/bdd-specs.md`

## Files to Modify/Create

- Modify: `backend/domain/repositories.py`
- Modify: `backend/application/service.py` (promote `360` to `RESEARCH_TIMEOUT_SECONDS`)

## Steps

### Step 1: Add Protocol methods
In `backend/domain/repositories.py`, add the following signatures (no bodies — these are `Protocol` definitions):

```python
class ProblemRepository(Protocol):
    # ... existing methods unchanged ...

    def list_being_researched(
        self, timeout_seconds: int = 360
    ) -> list["Problem"]:
        """Return Problems whose research_started_at is within the freshness window.

        A row is included iff research_started_at is non-null AND
        (utc_now() - research_started_at).total_seconds() < timeout_seconds.
        Order: research_started_at DESC.
        """
        ...


class ResearchCycleRepository(Protocol):
    # ... existing methods unchanged ...

    def get_latest_cycle_at(self) -> "datetime | None":
        """Return MAX(research_cycles.created_at) or None on empty table."""
        ...
```

### Step 2: Promote the timeout constant
In `backend/application/service.py`, replace the literal `360` in `_is_being_researched(problem, timeout_seconds=360)` with a module-level constant:

```python
RESEARCH_TIMEOUT_SECONDS: int = 360


def _is_being_researched(
    problem: Problem,
    timeout_seconds: int = RESEARCH_TIMEOUT_SECONDS,
) -> bool:
    ...
```

Update existing call sites at lines 625, 793, and 2384 to pass through `RESEARCH_TIMEOUT_SECONDS` only if they currently customise the timeout (they do not; the default is sufficient). Re-export the constant from `backend.application.service` so tests and the new repo method can import it via `from backend.application.service import RESEARCH_TIMEOUT_SECONDS`.

### Step 3: Verify nothing breaks
- `uv run ruff check --fix backend/domain/repositories.py backend/application/service.py`
- `uv run pytest backend/tests/unit -k "research" -x` — existing tests still pass.

## Verification Commands

```bash
uv run ruff check backend/domain/repositories.py backend/application/service.py
uv run python -c "from backend.application.service import RESEARCH_TIMEOUT_SECONDS; assert RESEARCH_TIMEOUT_SECONDS == 360"
uv run python -c "from backend.domain.repositories import ProblemRepository, ResearchCycleRepository; assert hasattr(ProblemRepository, 'list_being_researched'); assert hasattr(ResearchCycleRepository, 'get_latest_cycle_at')"
uv run pytest backend/tests/unit -k "research" -x
```

## Success Criteria

- Both Protocol methods present with exact signatures shown above.
- `RESEARCH_TIMEOUT_SECONDS = 360` exported from `backend.application.service`.
- `_is_being_researched` default uses the constant, no remaining literal `360` in this file.
- All existing unit tests still pass.
- No implementation bodies added (`...` only in Protocol).
