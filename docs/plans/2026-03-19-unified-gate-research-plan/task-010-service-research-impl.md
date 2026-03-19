# Task 010: Service — Auto Research — Implementation

**depends-on**: task-010-service-research-test

## Description

Update `improve_solution()` to use strict hill-climbing with content regression/bloat filters and set `problem.canonical_solution_id` on success. Update `synthesize_solutions()` to set `problem.canonical_solution_id`. Update `find_research_candidates()` to filter by cooldown. These methods already exist but need to be adapted for the unified model.

## Execution Context

**Task Number**: 010b of 016
**Phase**: Application Layer — Auto Research
**Prerequisites**: Task 010 tests written (Red).

## BDD Scenario

```gherkin
Scenario: Hill-climbing accepts improvement with strictly higher confidence
  Given "sol-1" has confidence 0.4
  When improve_solution creates "sol-2" with confidence 0.5
  Then "sol-1".canonical_id = "sol-2"
  And problem.best_confidence = 0.5
  And problem.canonical_solution_id = "sol-2"
  And status = "improved"
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 2 + Feature 4)

## Files to Modify/Create

- Modify: `app/application/service.py`

## Steps

### Step 1: Update `improve_solution()`

Ensure these behaviors are correct:
- Create new Solution with `parent_solution_id = current_solution.solution_id`
- Strict `>` comparison: accept only when `new_confidence > current_best_confidence`
- Content regression check: reject if `len(improved_content) < 0.5 * len(original_content)` and `len(improved_steps) <= len(original_steps)`
- Content bloat check: reject if `len(improved_content) > 2 * len(original_content)` and `new_confidence - current_best_confidence <= 0.05`
- On acceptance: mark old solution with `canonical_id = new_solution.solution_id`; update `problem.best_confidence`; set `problem.canonical_solution_id = new_solution.solution_id`
- Optimistic locking: catch `ConcurrentModificationError` on `_problems.update()`, retry up to 3 times with exponential backoff (0.1s, 0.2s, 0.4s base + 0-50ms jitter)
- Cycle detection: walk `parent_solution_id` ancestry before creating new solution; verify no cycle

### Step 2: Update `synthesize_solutions()`

Ensure the method sets `problem.canonical_solution_id = canonical.solution_id` after creating the canonical solution.

The canonical solution must have `review_status = "approved"` (auto-approved; system-generated).

### Step 3: Update `find_research_candidates()`

Update `find_research_candidates(limit, cooldown_hours=6) -> list[dict]`:
- Delegate to `self._problems.find_research_candidates(limit=limit)`
- For each candidate, check `self._research_cycles.last_researched_at(problem.problem_id)`
- Exclude problems researched within `cooldown_hours`

### Step 4: Run tests (Green)

**Verification**: Run `uv run pytest tests/unit/test_service_research.py -v --tb=short` and verify all pass.

### Step 5: Run full unit tests

**Verification**: Run `uv run pytest tests/unit/ -q --tb=short` and verify no regressions.

## Verification Commands

```bash
uv run pytest tests/unit/test_service_research.py -v --tb=short
uv run pytest tests/unit/ -q --tb=short
```

## Success Criteria

- All `test_service_research.py` tests pass
- `improve_solution()` sets `problem.canonical_solution_id` on accepted improvement
- `synthesize_solutions()` sets `problem.canonical_solution_id`
- Hill-climbing uses strict `>` comparison throughout
