# Task 004: In-Memory Repositories — Implementation

**depends-on**: task-004-in-memory-repos-test

## Description

Update `app/infrastructure/persistence/in_memory.py` to remove V1 repository classes (InMemoryThreadRepository, InMemoryCommentRepository, InMemoryVoteRepository) and implement all new methods on the Problem, Solution, and TokenTransaction in-memory repositories.

## Execution Context

**Task Number**: 004b of 016
**Phase**: Foundation — Infrastructure (In-Memory Repos)
**Prerequisites**: Task 004 tests written (Red).

## BDD Scenario

```gherkin
Scenario: Only approved content is visible in list endpoints
  Given the in-memory repositories are used
  When find_unreviewed is called
  Then only problems/solutions with review_status=None or "error" are returned

Scenario: Problem with low confidence appears as research candidate
  Given problem "prob-1" has best_confidence 0.2 and solution_count 1
  When find_research_candidates is called with limit=10
  Then "prob-1" appears in the candidate list
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature`

## Files to Modify/Create

- Modify: `app/infrastructure/persistence/in_memory.py`

## Steps

### Step 1: Read `in_memory.py` thoroughly

Understand the existing structure before making changes.

### Step 2: Remove V1 repository classes

Delete `InMemoryThreadRepository`, `InMemoryCommentRepository`, and `InMemoryVoteRepository` classes entirely.

### Step 3: Update `InMemoryProblemRepository`

Add these methods:
- `delete(problem_id: UUID) -> None`: remove the problem from the internal store
- `find_unreviewed(limit: int, retry_error_before: datetime | None = None) -> list[Problem]`: return problems where `review_status is None`, plus those with `review_status == "error"` if `retry_error_before` is set and the problem's `reviewed_at` is before that timestamp
- `find_similar(embedding: list[float], threshold: float) -> list[Problem]`: return problems whose embedding cosine similarity exceeds threshold (use simple dot product for in-memory; return empty list if problem has no embedding)
- `find_research_candidates(limit: int = 10, offset: int = 0) -> list[Problem]`: return problems sorted by `solution_count DESC, best_confidence ASC`, limited to `limit`; filter out problems recently researched (implemented at service layer, not here)

### Step 4: Update `InMemorySolutionRepository`

Add these methods:
- `delete(solution_id: UUID) -> None`: remove the solution
- `find_unreviewed(limit: int, retry_error_before: datetime | None = None) -> list[Solution]`: same logic as Problem version
- `list_by_problem_ranked(problem_id: UUID) -> list[Solution]`: return approved solutions for a problem, sorted by `confidence DESC`
- `find_superseded(problem_id: UUID) -> list[Solution]`: return solutions where `canonical_id is not None` for the given problem

### Step 5: Update `InMemoryTokenTransactionRepository`

Rename `clear_related_comment(comment_id)` to `clear_related_solution(solution_id)`. Update internal field reference from `related_comment_id` to `related_solution_id`.

### Step 6: Run tests (Green)

**Verification**: Run `uv run pytest tests/unit/test_in_memory_repos.py -v --tb=short` and verify all pass.

### Step 7: Run full unit suite

**Verification**: Run `uv run pytest tests/unit/ -q --tb=short` and verify no new failures.

## Verification Commands

```bash
uv run pytest tests/unit/test_in_memory_repos.py -v --tb=short
uv run pytest tests/unit/ -q --tb=short
```

## Success Criteria

- All `test_in_memory_repos.py` tests pass
- V1 in-memory repository classes removed
- All new repository methods implemented correctly
