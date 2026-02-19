# Task 003 — Test: V2 Repository Protocol Interfaces

**Type:** Red (test first)
**Depends-on:** task-002
**BDD refs:** Feature 1 Scenario "Successful semantic match", Feature 2 Scenario "Duplicate detection", Feature 3 Scenario "Multiple outcome reports aggregate correctly"

## Goal

Write failing unit tests for the three new repository protocols (`ProblemRepository`, `SolutionRepository`, `OutcomeRepository`) using in-memory implementations. Tests should verify the protocol contract, not the SQL implementation.

## What to test

### ProblemRepository
- `add(problem)` — stores problem, retrievable by ID
- `get(problem_id)` — returns `Problem | None`
- `list_all()` — returns all problems
- `find_similar(embedding, threshold)` — returns problems above similarity threshold (use cosine sim stub returning 1.0 for identical embeddings)
- `find_by_error_signature(signature)` — exact match on `error_signature` field
- `update(problem)` — overwrites existing problem

### SolutionRepository
- `add(solution)` — stores solution
- `get(solution_id)` — returns `Solution | None`
- `list_by_problem(problem_id)` — returns all solutions for a problem, ordered by confidence desc
- `find_canonical_candidates(problem_id, similarity_threshold)` — returns non-canonical solutions with pairwise similarity above threshold
- `update(solution)` — overwrites existing solution

### OutcomeRepository
- `add(outcome)` — stores outcome
- `list_by_solution(solution_id)` — returns all outcomes for a solution
- `count_by_reporter(reporter_id, since)` — returns outcome count for rate limiting

## Files to create

- `tests/unit/test_repositories_v2.py`

## Verification

```bash
uv run pytest tests/unit/test_repositories_v2.py -v
```

Tests must fail (red) before implementation begins.
