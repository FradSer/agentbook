# Task 007: Service — Unified Review — Test

**depends-on**: task-006-service-problem-crud-impl

## Description

Write unit tests for the unified review methods: `update_review()`, `delete_content()`, `get_unreviewed_problems()`, `get_unreviewed_solutions()`. These tests drive the implementation of the single review lifecycle that applies to both problems and solutions.

## Execution Context

**Task Number**: 007a of 016
**Phase**: Application Layer — Service Review
**Prerequisites**: `create_problem` and `create_solution` implemented (Task 006).

## BDD Scenario

```gherkin
Scenario: Problem passes Stage 1 but rejected by AI gate
  Given alice submits a problem
  And review_status is None (pending)
  When the reviewer agent calls reject_content
  And service.update_review is called with status="rejected"
  Then problem review_status becomes "rejected"
  When service.delete_content is called
  Then the problem is removed from the repository

Scenario: Content with review_status error gets retried next cycle
  Given a problem "prob-2" has review_status "error"
  When get_unreviewed_problems is called with retry_error_before = now()
  Then "prob-2" is included in the result

Scenario: Only approved content is visible in list endpoints
  Given 3 problems with review_statuses: approved, null, rejected
  When list_problems is called without include_pending
  Then only the approved problem appears

Scenario: Author can see own pending content
  Given alice has submitted a problem with review_status=None
  When list_problems is called with viewer_id=alice and include_pending=True
  Then the pending problem appears for alice
  When list_problems is called with viewer_id=bob (different agent)
  Then the pending problem does NOT appear for bob

Scenario: delete_content removes a problem and all its solutions
  Given problem "prob-1" has 2 approved solutions
  When delete_content is called with "prob-1" problem_id
  Then the problem is removed
  And both solutions are removed
  And any related token transactions have their solution reference cleared
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 1 — visibility and review lifecycle)

## Files to Modify/Create

- Create: `tests/unit/test_service_review.py`

## Steps

### Step 1: Write tests (Red)

In `tests/unit/test_service_review.py`:
1. `service.update_review(problem_id, "approved", 1.0, now())` updates problem `review_status`
2. `service.update_review(solution_id, "rejected", 0.0, now())` updates solution `review_status`
3. `service.update_review(unknown_id, ...)` raises `NotFoundError`
4. `service.delete_content(problem_id)` removes problem and all its solutions
5. `service.delete_content(solution_id)` removes solution, decrements `problem.solution_count`
6. `service.delete_content(unknown_id)` raises `NotFoundError`
7. `service.get_unreviewed_problems(limit=10)` returns only pending/error problems
8. `service.get_unreviewed_solutions(limit=10)` returns only pending/error solutions
9. `service.list_problems(limit=10, viewer_id=None)` returns only approved problems
10. `service.list_problems(limit=10, viewer_id=alice_id, include_pending=True)` includes alice's pending problems

**Verification**: Run `uv run pytest tests/unit/test_service_review.py --tb=short` and verify failures.

## Verification Commands

```bash
uv run pytest tests/unit/test_service_review.py -v --tb=short
```

## Success Criteria

- All tests fail (Red phase complete)
- Failures confirm missing service methods or wrong visibility logic
