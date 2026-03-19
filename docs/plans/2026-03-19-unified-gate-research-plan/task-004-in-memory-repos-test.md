# Task 004: In-Memory Repositories — Test

**depends-on**: task-002-domain-models-impl

## Description

Write unit tests for the updated in-memory repository implementations. Tests cover the new methods added to `InMemoryProblemRepository` and `InMemorySolutionRepository` (`delete`, `find_unreviewed`, `find_research_candidates`, `find_similar`) and verify that V1 in-memory repositories are removed.

## Execution Context

**Task Number**: 004a of 016
**Phase**: Foundation — Infrastructure (In-Memory Repos)
**Prerequisites**: Domain models updated (Task 002 complete). This is independent of Task 003 (ORM).

## BDD Scenario

```gherkin
Scenario: Only approved content is visible in list endpoints
  Given alice has submitted 3 problems with different review statuses
  When the problem repository's list_all is called
  And the service filters by review_status == "approved"
  Then only the approved problem appears

Scenario: Content with review_status error gets retried next cycle
  Given a problem "prob-2" has review_status "error"
  When find_unreviewed is called with retry_error_before = now
  Then "prob-2" is included in the result batch

Scenario: Problem with low confidence appears as research candidate
  Given problem "prob-1" has best_confidence 0.2 and solution_count 1
  When find_research_candidates is called with limit=10
  Then "prob-1" appears in the candidate list
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 1 + Feature 4)

## Files to Modify/Create

- Create: `tests/unit/test_in_memory_repos.py`

## Steps

### Step 1: Write tests (Red)

In `tests/unit/test_in_memory_repos.py`, write tests for `InMemoryProblemRepository`:
1. `add()` and `get()` basic operations
2. `delete(problem_id)` removes the problem
3. `find_unreviewed(limit, retry_error_before)` returns problems with `review_status=None`
4. `find_unreviewed` also returns problems with `review_status="error"` when `retry_error_before` is set
5. `find_research_candidates(limit)` returns problems with low `best_confidence` or high `solution_count`
6. `find_similar(embedding, threshold)` returns problems with similar embeddings

For `InMemorySolutionRepository`:
1. `delete(solution_id)` removes the solution
2. `find_unreviewed(limit, retry_error_before)` returns solutions with `review_status=None` or `"error"`
3. `list_by_problem_ranked(problem_id)` returns approved solutions sorted by confidence descending
4. `find_superseded(problem_id)` returns solutions where `canonical_id is not None`

For `InMemoryTokenTransactionRepository`:
1. `clear_related_solution(solution_id)` sets `related_solution_id=None` for matching transactions (replaces old `clear_related_comment`)

Verify `InMemoryThreadRepository`, `InMemoryCommentRepository`, `InMemoryVoteRepository` do not exist.

**Verification**: Run `uv run pytest tests/unit/test_in_memory_repos.py --tb=short` and verify failures.

## Verification Commands

```bash
uv run pytest tests/unit/test_in_memory_repos.py -v --tb=short
```

## Success Criteria

- All `test_in_memory_repos.py` tests fail (Red phase complete)
- Failures confirm missing methods or wrong behavior in in-memory implementations
