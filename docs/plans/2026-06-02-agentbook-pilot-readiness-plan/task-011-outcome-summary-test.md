# Task 011 (outcome-summary) — Test (Red)

**type:** test
**theme:** P1-D
**closes:** PR-15
**depends-on:** [001]

## Goal

Write the failing (Red) BDD tests for the **Problem-level outcome_summary aggregates across all solutions** behavior. These tests encode the target contract and MUST fail against current `main` before the paired impl task (011-outcome-summary-impl) makes them pass.

## BDD Scenarios (source of truth)

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

- `backend/tests/features/outcome-summary.feature` — the Gherkin above, verbatim.
- `backend/tests/unit/test_outcome_summary.py` — step implementations / assertions. Isolate external dependencies (DB, Voyage, network) with in-memory repos and test doubles per `backend/tests/conftest.py` conventions; use the `enable_limiter` fixture only where a scenario asserts rate-limit behavior.

## Steps

1. Copy the scenarios above into `outcome-summary.feature`.
2. Implement step defs / test functions asserting the target contract (NOT current behavior). For cross-transport parity scenarios, assert REST and MCP payloads field-by-field via a shared helper.
3. Run the tests; confirm they FAIL (Red) for the documented reason (current behavior diverges).

## Verification

```bash
uv run pytest backend/tests/unit/test_outcome_summary.py -q   # expect FAIL (Red) before impl
```
