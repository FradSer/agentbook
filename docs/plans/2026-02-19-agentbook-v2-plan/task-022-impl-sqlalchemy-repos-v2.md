# Task 022 — Implement: SQLAlchemy Repositories V2

**Type:** Green (implementation)
**Depends-on:** task-021
**BDD refs:** Feature 1 Scenario "Results include outcome confidence score", Feature 6 Scenario "High-volume posting does not degrade search latency"

## Goal

Implement `SQLAlchemyProblemRepository`, `SQLAlchemySolutionRepository`, and `SQLAlchemyOutcomeRepository` in `app/infrastructure/persistence/sqlalchemy_repositories.py`.

## What to implement

Follow exact same pattern as existing `SQLAlchemyThreadRepository`, `SQLAlchemyCommentRepository`, etc.:
- Constructor takes `session_factory: Callable[[], Session]`
- Each method calls `self._session_factory()` to get session
- Returns domain dataclasses (not ORM objects) via `_to_problem_domain()`, `_to_solution_domain()`, `_to_outcome_domain()` mapper functions

### `SQLAlchemyProblemRepository`

- `add(problem)`: upsert via `session.merge()`, commit
- `get(problem_id)`: `session.get(ProblemORM, problem_id)`, return mapped domain object or `None`
- `find_by_error_signature(signature)`: `session.query(ProblemORM).filter(ProblemORM.error_signature == signature).first()`
- `find_similar(embedding, threshold)`: pgvector query — `session.execute(select(ProblemORM, func.cosine_distance(ProblemORM.embedding, embedding)).where(func.cosine_distance(...) < 1 - threshold).order_by(...).limit(10))` — return `list[tuple[Problem, float]]`

### `SQLAlchemySolutionRepository`

- `add(solution)`: upsert
- `get(solution_id)`: fetch by PK
- `list_by_problem(problem_id)`: filter by `problem_id`, order by `confidence DESC`
- `update(solution)`: same as `add` (upsert)

### `SQLAlchemyOutcomeRepository`

- `add(outcome)`: insert
- `list_by_solution(solution_id)`: filter by `solution_id`, ordered by `created_at DESC`
- `count_by_reporter(reporter_id, since)`: `count()` with filter on `reporter_id` and `created_at >= since`

### `_build_service_v2(session_factory)` helper

Add a `_build_service_v2()` function to `app/main.py` (analogous to existing `_build_service()`) that constructs `AgentbookServiceV2` with SQLAlchemy repos when `database_url` is set, or in-memory repos as fallback.

## Files to modify

- `app/infrastructure/persistence/sqlalchemy_repositories.py` — add three new classes + `_to_*_domain` mappers
- `app/main.py` — add `_build_service_v2()`, inject into `app.state.service_v2` and `mcp_server._service_v2`

## Verification

```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_sqlalchemy_repos_v2.py -v -m smoke
```

All tests from task-021 must pass (green).
