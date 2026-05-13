# Task 004b: Repository methods (in-memory + SQLAlchemy) — Green

**depends-on**: 004a, 003

## Description

Implement `ProblemRepository.list_being_researched` and `ResearchCycleRepository.get_latest_cycle_at` in both the in-memory and SQLAlchemy persistence layers, turning the 10 tests from task 004a from Red to Green. Depends on 003 because the SQLAlchemy implementation runs faster against the partial index (correctness without the index, performance with it).

## Execution Context

**Task Number**: 004b of 20
**Phase**: Domain Repository — Green
**Prerequisites**: Task 004a (failing tests), Task 003 (migration).

## BDD Scenario

(Same scenarios as 004a — this task makes them PASS.)

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
```

## Files to Modify/Create

- Modify: `backend/infrastructure/persistence/in_memory.py`
- Modify: `backend/infrastructure/persistence/sqlalchemy_repositories.py`

## Steps

### Step 1: In-memory implementation

In `backend/infrastructure/persistence/in_memory.py`:

```python
# Inside InMemoryProblemRepository:
def list_being_researched(
    self, timeout_seconds: int = RESEARCH_TIMEOUT_SECONDS
) -> list[Problem]:
    """Returns Problems whose research_started_at is within the window.

    Filter: research_started_at is non-null AND fresher than timeout_seconds.
    Order: research_started_at DESC (deterministic across workers).
    """
    ...  # implementation body in this task only

# Inside InMemoryResearchCycleRepository:
def get_latest_cycle_at(self) -> datetime | None:
    """Returns MAX(created_at) across all stored cycles, or None if empty."""
    ...
```

Import `RESEARCH_TIMEOUT_SECONDS` from `backend.application.service`.

### Step 2: SQLAlchemy implementation

In `backend/infrastructure/persistence/sqlalchemy_repositories.py`:

```python
# Inside SQLAlchemyProblemRepository:
def list_being_researched(
    self, timeout_seconds: int = RESEARCH_TIMEOUT_SECONDS
) -> list[Problem]:
    """SELECT … WHERE research_started_at IS NOT NULL
       AND research_started_at > now() - make_interval(secs => :timeout)
       ORDER BY research_started_at DESC.

    Reuses _to_problem_domain for hydration.
    """
    ...

# Inside SQLAlchemyResearchCycleRepository:
def get_latest_cycle_at(self) -> datetime | None:
    """SELECT MAX(created_at) FROM research_cycles."""
    ...
```

Use `func.now() - func.make_interval(secs=timeout_seconds)` so the comparison happens server-side (avoids client-clock skew in horizontal scaling).

### Step 3: Run tests to confirm Green
```bash
uv run pytest backend/tests/unit/test_in_memory_repos.py -k "list_being_researched or get_latest_cycle_at" -x
RUN_DOCKER_TESTS=1 uv run pytest backend/tests/integration/test_sqlalchemy_repos.py -k "list_being_researched or get_latest_cycle_at" -x
```

Both suites must PASS.

### Step 4: Format and lint
```bash
uv run ruff format backend/infrastructure/persistence/
uv run ruff check --fix backend/infrastructure/persistence/
```

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_in_memory_repos.py -k "list_being_researched or get_latest_cycle_at" -x
RUN_DOCKER_TESTS=1 uv run pytest backend/tests/integration/test_sqlalchemy_repos.py -k "list_being_researched or get_latest_cycle_at" -x
uv run ruff check backend/infrastructure/persistence/
```

## Success Criteria

- 5/5 in-memory tests pass.
- 5/5 SQLAlchemy integration tests pass against Postgres.
- The SQLAlchemy filter uses `func.now()` server-side, not Python `datetime.utcnow()` client-side.
- Result ordering is `research_started_at DESC` for both impls.
- No new dependency added.
- Ruff format + check both pass.
