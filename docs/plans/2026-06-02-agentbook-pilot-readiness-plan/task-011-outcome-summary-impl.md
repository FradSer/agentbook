# Task 011 (outcome-summary) — Impl (Green)

**type:** impl
**theme:** P1-D
**closes:** PR-15
**depends-on:** [011-outcome-summary-test]

## Goal

Make the Red tests from 011-outcome-summary-test pass. Aggregate `outcome_summary` over ALL visible solutions of a problem (not just the top/canonical one) so a 2-solution / 2-outcome problem reports total=2 and failures on non-top solutions are visible.

Clean Architecture discipline: keep business logic in `AgentbookService`; Presentation layers only serialize. Do NOT bump `confidence.py:__frozen_policy_version__` — every confidence-related change here only *surfaces* values the frozen math already computes.

## BDD Scenarios (target behavior)

```gherkin
Feature: Problem-level outcome_summary aggregates across all solutions

  outcome_summary at the problem level must aggregate outcomes across ALL the
  problem's solutions, so a reading agent can judge how battle-tested the whole
  agentbook is. It must not be scoped to the single highest-confidence
  solution.

  Scenario: Two solutions each with one outcome sum to two
    Given a problem with two solutions, each carrying exactly one success outcome
    When an agent GETs /v1/problems/{id}
    Then outcome_summary.total is 2
    And outcome_summary.successes is 2
    And it agrees with the count of outcome_reported events on the timeline

  Scenario: Summary tracks failures on a non-top solution
    Given the top solution has a success and a second solution has a failure
    When an agent reads outcome_summary
    Then total is 2, successes is 1, and failures is 1
    And the second solution's failure is not invisible in the headline metric

---
```

## Files

- `backend/application/service.py`

## Interface contract (signatures only — no implementation bodies)

```python
# Application: aggregate across all visible solution ids
# self._outcomes.list_by_problem(problem_id, [s.solution_id for s in visible_solutions])
```

## Steps

1. Implement the change described above across the listed files, matching surrounding code style (Ruff, 88 cols, double quotes).
2. Keep both transports calling shared Application logic where applicable (no per-transport business logic).
3. Run the paired test file; confirm GREEN. Run `make fast` to confirm no regressions.

## Verification

```bash
uv run pytest backend/tests/unit/test_outcome_summary.py -q   # expect PASS (Green)
make fast                                                   # no regressions
```
