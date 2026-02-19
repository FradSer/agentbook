# Task 016 — Implement: AgentbookServiceV2.get_context()

**Type:** Green (implementation)
**Depends-on:** task-015
**BDD refs:** Feature 5 Scenario "Agent gets related problems alongside solution", Feature 5 Scenario "Tag-based navigation"

## Goal

Add `get_context()` to `AgentbookServiceV2` in `app/application/service_v2.py`.

## What to implement

### `get_context(id: str, include: list[str] | None) -> dict`

**Algorithm:**
1. Parse `id` as UUID — raise `ValueError` if unparseable
2. Attempt `problems.get(uuid_id)` — if found, type is `"problem"`
3. Else attempt `solutions.get(uuid_id)` — if found, type is `"solution"`
4. Else raise `NotFoundError`

**If problem:**
- `include` defaults to `["solutions", "similar", "related"]`
- Fetch `solutions.list_by_problem(problem_id)` if "solutions" in include
- Fetch `problems.find_similar(problem.embedding, threshold=0.6)` and exclude self if "similar" in include
- Fetch related problems from `problems.get_related(problem_id)` if "related" in include (method returns list of `(Problem, relationship_type)` tuples)

**If solution:**
- `include` defaults to `["outcomes", "problem"]`
- Fetch `outcomes.list_by_solution(solution_id)` if "outcomes" in include
- Fetch parent problem if "problem" in include

**Return shape:** `{"type": ..., "data": {serialized entity}, "solutions"?: [...], "outcomes"?: [...], "similar"?: [...], "related_problems"?: [...]}`

## Files to modify

- `app/application/service_v2.py` — add `get_context()` method
- `app/domain/repositories.py` — add `get_related(problem_id)` method to `ProblemRepository` protocol
- `app/infrastructure/persistence/in_memory.py` — add `get_related()` to `InMemoryProblemRepository` (simple dict of relationships)

## Verification

```bash
uv run pytest tests/unit/test_service_get_context.py -v
```

All tests from task-015 must pass (green).
