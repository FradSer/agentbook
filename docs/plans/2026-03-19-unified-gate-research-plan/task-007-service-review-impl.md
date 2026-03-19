# Task 007: Service — Unified Review — Implementation

**depends-on**: task-007-service-review-test

## Description

Implement `update_review()`, `delete_content()`, `get_unreviewed_problems()`, `get_unreviewed_solutions()` in `AgentbookService`. Update `list_problems()` to use the unified visibility logic. Remove the old `update_thread_review()`, `update_comment_review()`, `delete_thread()`, `delete_comment()` methods.

## Execution Context

**Task Number**: 007b of 016
**Phase**: Application Layer — Service Review
**Prerequisites**: Task 007 tests written (Red).

## BDD Scenario

```gherkin
Scenario: Unified update_review works for both content types
  Given a problem ID and a solution ID exist
  When update_review is called with the problem ID
  Then problem.review_status is updated
  When update_review is called with the solution ID
  Then solution.review_status is updated
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 1)

## Files to Modify/Create

- Modify: `app/application/service.py`

## Steps

### Step 1: Implement `update_review()`

Add `update_review(content_id: UUID, status: str, score: float, reviewed_at: datetime) -> Problem | Solution`:
- Try `self._problems.get(content_id)` first; if found, update review fields and call `self._problems.update()`
- Else try `self._solutions.get(content_id)`; if found, update review fields and call `self._solutions.update()`
- Else raise `NotFoundError`

### Step 2: Implement `delete_content()`

Add `delete_content(content_id: UUID) -> None`:
- Try `self._problems.get(content_id)` first; if problem, cascade delete all solutions (clear transaction refs first), then delete problem
- Else try `self._solutions.get(content_id)`; if solution, clear transaction refs, delete solution, decrement `problem.solution_count`
- Else raise `NotFoundError`

### Step 3: Implement review query methods

Add:
- `get_unreviewed_problems(limit=100, retry_error_before=None) -> list[Problem]`: delegate to `self._problems.find_unreviewed(...)`
- `get_unreviewed_solutions(limit=100, retry_error_before=None) -> list[Solution]`: delegate to `self._solutions.find_unreviewed(...)`

### Step 4: Update `list_problems()` visibility

Update `list_problems(limit, viewer_id=None, include_pending=False) -> dict`:
- A problem is visible if it is approved, OR if `include_pending=True` and `viewer_id == problem.author_id`
- Return problem data including `has_canonical: bool`, `best_confidence`, `solution_count`, `review_status`

### Step 5: Add private helpers

Add or update:
- `_is_approved(content: Problem | Solution) -> bool`: returns `content.review_status == "approved"`
- `_can_view_problem(problem, viewer_id) -> bool`: returns True if approved, or viewer is author
- `_normalize_review_status(status) -> str`: returns `"pending"` when status is None

### Step 6: Run tests (Green)

**Verification**: Run `uv run pytest tests/unit/test_service_review.py -v --tb=short` and verify all pass.

## Verification Commands

```bash
uv run pytest tests/unit/test_service_review.py -v --tb=short
uv run pytest tests/unit/ -q --tb=short
```

## Success Criteria

- All `test_service_review.py` tests pass
- `update_review()`, `delete_content()` implemented as unified methods
- Visibility logic in `list_problems()` works for approved + pending (author only)
