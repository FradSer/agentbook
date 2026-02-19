# Task 004 — Implement: V2 Repository Protocols and In-Memory Implementations

**Type:** Green (implementation)
**Depends-on:** task-003
**BDD refs:** Feature 1 Scenario "Successful semantic match", Feature 2 Scenario "Duplicate detection", Feature 3 Scenario "Multiple outcome reports aggregate correctly"

## Goal

Define three new `typing.Protocol` interfaces in `app/domain/repositories.py` and implement them as in-memory classes in `app/infrastructure/persistence/in_memory.py`.

## What to implement

### In `app/domain/repositories.py`

Add three new `Protocol` classes: `ProblemRepository`, `SolutionRepository`, `OutcomeRepository`. Each method signature must match the contract tested in task-003.

For `ProblemRepository.find_similar(embedding, threshold)`: the protocol signature accepts a `list[float]` embedding and float threshold, returns `list[tuple[Problem, float]]` (problem, similarity score).

### In `app/infrastructure/persistence/in_memory.py`

Add three new in-memory implementations:

- `InMemoryProblemRepository`: stores in a dict keyed by `problem_id`. `find_similar` computes cosine similarity inline for test purposes (import numpy only if available, otherwise fallback to dot product / magnitude computation).
- `InMemorySolutionRepository`: stores in a dict, `list_by_problem` filters and sorts by `confidence` descending.
- `InMemoryOutcomeRepository`: stores in a list, `list_by_solution` filters, `count_by_reporter` filters and counts.

## Constraints

- Do NOT remove existing repository protocols or in-memory implementations yet
- Protocol definitions must be compatible with `typing.Protocol` (no `ABC`)

## Files to modify

- `app/domain/repositories.py` — add three new Protocol classes
- `app/infrastructure/persistence/in_memory.py` — add three new in-memory classes

## Verification

```bash
uv run pytest tests/unit/test_repositories_v2.py -v
```

All tests from task-003 must pass (green).
