# Task 004a: Repository methods (in-memory + SQLAlchemy) — Red

**depends-on**: 002

## Description

Add failing tests for the two new repository methods declared in task 002: `ProblemRepository.list_being_researched` and `ResearchCycleRepository.get_latest_cycle_at`. Cover both the in-memory implementation (unit, no Postgres) and the SQLAlchemy implementation (integration, requires Postgres + `RUN_DOCKER_TESTS=1`). Tests must FAIL until task 004b lands.

## Execution Context

**Task Number**: 004a of 20
**Phase**: Domain Repository — Red
**Prerequisites**: Task 002 declared the Protocol signatures.

## BDD Scenario

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

- Modify: `backend/tests/unit/test_in_memory_repos.py` (add cases)
- Modify: `backend/tests/integration/test_sqlalchemy_repos.py` (add cases)

## Steps

### Step 1: Verify scenarios match the feature file
Run `grep -n "list_being_researched\|get_latest_cycle_at" backend/tests/features/live_research_banner.feature` and confirm both scenarios are present.

### Step 2: Add in-memory tests (Red)

In `backend/tests/unit/test_in_memory_repos.py`, add the following test contracts (no implementation):

```python
def test_list_being_researched_includes_only_fresh_rows():
    """Asserts: window-edge inclusion (359s) and exclusion (361s + NULL)."""
    ...

def test_list_being_researched_orders_by_research_started_at_desc():
    """Two fresh rows return in descending start time."""
    ...

def test_list_being_researched_empty_when_no_active():
    """Returns [] when every Problem has research_started_at IS NULL."""
    ...

def test_get_latest_cycle_at_returns_none_when_empty():
    """No ResearchCycle rows → None."""
    ...

def test_get_latest_cycle_at_returns_max_created_at():
    """Three cycles → the most recent one's created_at."""
    ...
```

### Step 3: Add SQLAlchemy integration tests (Red)

In `backend/tests/integration/test_sqlalchemy_repos.py`, add the same five contracts marked `@pytest.mark.smoke`. Use the existing Postgres fixture (`db_session` or equivalent in that file). Test data must be inserted via the existing factory helpers; do not raw-SQL insert.

### Step 4: Confirm Red
```bash
uv run pytest backend/tests/unit/test_in_memory_repos.py -k "list_being_researched or get_latest_cycle_at" -x
RUN_DOCKER_TESTS=1 uv run pytest backend/tests/integration/test_sqlalchemy_repos.py -k "list_being_researched or get_latest_cycle_at" -x
```

Both must FAIL with `AttributeError: '...Repository' object has no attribute 'list_being_researched'` (or `get_latest_cycle_at`).

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_in_memory_repos.py -k "list_being_researched or get_latest_cycle_at" -x
# Expected: FAILED (5 tests, AttributeError on missing methods)

# Optional integration (requires Docker + Postgres)
RUN_DOCKER_TESTS=1 uv run pytest backend/tests/integration/test_sqlalchemy_repos.py -k "list_being_researched or get_latest_cycle_at" -x
# Expected: FAILED
```

## Success Criteria

- 5 unit tests added in `test_in_memory_repos.py`, all FAIL for the intended reason.
- 5 integration tests added in `test_sqlalchemy_repos.py`, all FAIL for the intended reason.
- No production code modified in this task.
- Tests use the existing in-memory repo fixture and the existing Postgres fixture; no test scaffolding rewrite.
