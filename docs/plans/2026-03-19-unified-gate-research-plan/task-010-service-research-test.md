# Task 010: Service — Auto Research — Test

**depends-on**: task-009-service-outcomes-impl

## Description

Write unit tests for the hill-climbing and research methods: `improve_solution()` (strict `>` comparison, content regression filter, content bloat filter, cycle detection), `synthesize_solutions()` (canonical solution creation, `problem.canonical_solution_id` update), `find_research_candidates()` (cooldown enforcement), and `get_solution_lineage()`.

## Execution Context

**Task Number**: 010a of 016
**Phase**: Application Layer — Auto Research
**Prerequisites**: Outcome-based confidence implemented (Task 009).

## BDD Scenario

```gherkin
Scenario: Hill-climbing accepts improvement with strictly higher confidence
  Given "sol-1" has confidence 0.4
  And a proposed "sol-2" has confidence 0.5
  When improve_solution is evaluated for "sol-2"
  Then "sol-1" is marked as superseded (canonical_id = sol-2)
  And problem.best_confidence updated to 0.5
  And status is "improved"

Scenario: Hill-climbing rejects equal confidence
  Given "sol-1" and proposed "sol-2" both have confidence 0.5
  When improve_solution evaluates "sol-2"
  Then "sol-2" is marked superseded (canonical_id = sol-1)
  And status is "no_improvement"

Scenario: Content regression filter rejects too-short improvements
  Given "sol-1" has 500 characters and 3 steps
  When improve_solution is called with "Short fix" (9 chars) and 1 step
  Then status is "no_improvement"
  And new content is less than 50% the length of the original

Scenario: Content bloat filter rejects inflated improvements
  Given "sol-1" has 200 characters and confidence 0.5
  When improve_solution is called with 500 characters and confidence 0.52
  Then status is "no_improvement"
  And content length is more than 2x original with confidence gain less than 0.05

Scenario: Cycle detection prevents self-referencing parent chain
  Given sol-2 has parent = sol-1, sol-1 has parent = null
  When improve_solution creates sol-3 with parent = sol-2
  Then the lineage sol-3 -> sol-2 -> sol-1 -> null is valid (no cycle)
  And the improvement proceeds

Scenario: Synthesis creates canonical solution
  Given problem "prob-1" has 10 active solutions
  When synthesize_solutions is called
  Then a new Solution is created by SYSTEM_AGENT_ID
  And the new Solution's review_status is "approved"
  And all 10 source solutions have canonical_id pointing to the new canonical
  And problem.canonical_solution_id is set to the new canonical solution_id

Scenario: Problem researched within cooldown is skipped
  Given problem "prob-1" was last researched 2 hours ago
  And cooldown_hours=6
  When find_research_candidates is called with cooldown_hours=6
  Then "prob-1" is not in the results

Scenario: Concurrent improvement retries with backoff
  Given a ConcurrentModificationError is raised on Problem.update
  When improve_solution is retried
  Then up to 3 retry attempts are made with exponential backoff
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 2 — hill-climbing; Feature 4 — Auto Research)

## Files to Modify/Create

- Create: `tests/unit/test_service_research.py`

## Steps

### Step 1: Write tests (Red)

In `tests/unit/test_service_research.py`:
1. Hill-climbing: `improve_solution()` with strictly higher confidence → `status="improved"`
2. Hill-climbing: equal confidence → `status="no_improvement"` (strict `>` not `>=`)
3. Hill-climbing: lower confidence → `status="no_improvement"`
4. Content regression: content < 50% original length without more steps → rejected
5. Content bloat: content > 2x original with < 0.05 confidence gain → rejected
6. Cycle detection: valid lineage proceeds; monkeypatch `_problems.update` to raise `ConcurrentModificationError` and verify retry
7. Synthesis: verify `synthesize_solutions()` creates canonical solution and sets `problem.canonical_solution_id`
8. `find_research_candidates(limit, cooldown_hours)` excludes problems with recent research cycle
9. `get_solution_lineage(solution_id)` returns chain from current solution back to root

**Verification**: Run `uv run pytest tests/unit/test_service_research.py --tb=short` and verify failures.

## Verification Commands

```bash
uv run pytest tests/unit/test_service_research.py -v --tb=short
```

## Success Criteria

- All tests fail (Red phase complete)
- Tests cover all hill-climbing guard rails and research candidate filtering
