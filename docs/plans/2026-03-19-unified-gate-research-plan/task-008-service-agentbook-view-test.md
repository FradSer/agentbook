# Task 008: Service — Agentbook View — Test

**depends-on**: task-007-service-review-impl

## Description

Write unit tests for `get_agentbook()` (the primary read path showing canonical solution first), the adapted `search()` method (now returns problems with best solution), and the visibility rules ensuring only approved content appears.

## Execution Context

**Task Number**: 008a of 016
**Phase**: Application Layer — Agentbook View
**Prerequisites**: Service review methods implemented (Task 007).

## BDD Scenario

```gherkin
Scenario: After approval, solution appears in agentbook view
  Given problem "prob-1" has an approved solution "sol-1"
  When get_agentbook is called for "prob-1"
  Then "sol-1" appears in solution_history

Scenario: Unapproved solution is not visible in agentbook view
  Given problem "prob-1" has a pending solution "sol-2"
  When get_agentbook is called for "prob-1"
  Then "sol-2" does not appear in the response

Scenario: Canonical solution shown first in agentbook view
  Given problem "prob-1" has canonical_solution_id pointing to "canonical-1"
  And problem "prob-1" has 5 non-canonical approved solutions
  When get_agentbook is called for "prob-1"
  Then the response has canonical_solution = "canonical-1"
  And solution_history contains the 5 non-canonical solutions

Scenario: Only approved content visible in search endpoints
  Given an approved problem and a pending problem with similar descriptions
  When search is called
  Then only the approved problem appears in results

Scenario: get_agentbook raises NotFoundError for unknown problem
  When get_agentbook is called with a non-existent problem_id
  Then NotFoundError is raised
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 2 — visibility after approval; Feature 1 — search visibility)

## Files to Modify/Create

- Create: `tests/unit/test_service_agentbook_view.py`

## Steps

### Step 1: Write tests (Red)

In `tests/unit/test_service_agentbook_view.py`:
1. `service.get_agentbook(problem_id)` returns dict with keys: `problem_id`, `description`, `canonical_solution`, `solution_history`, `best_confidence`, `solution_count`
2. When `problem.canonical_solution_id` is set, `canonical_solution` is populated
3. When `problem.canonical_solution_id` is None, `canonical_solution` is None
4. Only approved solutions appear in `solution_history`
5. The canonical solution is NOT duplicated in `solution_history`
6. `service.get_agentbook(unknown_id)` raises `NotFoundError`
7. A pending problem is not visible via `get_agentbook` to non-author callers
8. `service.search(query, limit)` returns only approved problems
9. `service.search(query, limit)` result items include `best_solution` dict with `confidence`, `outcome_count`, `content_preview`

**Verification**: Run `uv run pytest tests/unit/test_service_agentbook_view.py --tb=short` and verify failures.

## Verification Commands

```bash
uv run pytest tests/unit/test_service_agentbook_view.py -v --tb=short
```

## Success Criteria

- All tests fail (Red phase complete)
- Failures confirm `get_agentbook()` does not exist or returns wrong structure
