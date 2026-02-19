# Task 021 — Test: SQLAlchemy Repositories V2

**Type:** Red (test first, integration)
**Depends-on:** task-020
**BDD refs:** Feature 1 Scenario "Successful semantic match with environment filter", Feature 6 Scenario "High-volume posting does not degrade search latency"

## Goal

Write failing integration tests for the SQLAlchemy implementations of `ProblemRepository`, `SolutionRepository`, and `OutcomeRepository` against a real PostgreSQL database.

## Test setup

These are integration tests requiring Docker (marked `@pytest.mark.smoke`):
- `RUN_DOCKER_TESTS=1` environment variable required
- Use a test database with v2 migration applied
- Each test wrapped in a transaction that rolls back after the test

## What to test

### `SQLAlchemyProblemRepository`
- `add(problem)` → persists to DB, `get(problem_id)` retrieves it
- `find_by_error_signature(sig)` → exact match query, returns matching problem
- `find_similar(embedding, threshold)` → pgvector cosine similarity query returns correct results
- `find_similar` performance: 1000 problems seeded, query returns in < 200ms

### `SQLAlchemySolutionRepository`
- `add(solution)` → persists, `get(solution_id)` retrieves
- `list_by_problem(problem_id)` → returns all solutions sorted by confidence descending
- `update(solution)` → mutates existing record (confidence update)

### `OutcomeRepository`
- `add(outcome)` → persists
- `list_by_solution(solution_id)` → returns all outcomes for solution
- `count_by_reporter(reporter_id, since=now-1h)` → correct count for rate limiting

## Files to create

- `tests/integration/test_sqlalchemy_repos_v2.py`

## Verification

```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_sqlalchemy_repos_v2.py -v -m smoke
```

Tests must fail (red) before implementation of task-022.
