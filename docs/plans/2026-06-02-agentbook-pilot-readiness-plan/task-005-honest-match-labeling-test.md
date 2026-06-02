# Task 005 (honest-match-labeling) — Test (Red)

**type:** test
**theme:** P1-D
**closes:** PR-14
**depends-on:** [001]

## Goal

Write the failing (Red) BDD tests for the **Honest match labeling on the read contract** behavior. These tests encode the target contract and MUST fail against current `main` before the paired impl task (005-honest-match-labeling-impl) makes them pass.

## BDD Scenarios (source of truth)

```gherkin
Feature: Honest match labeling on the read contract

  An agent filters on match_quality / no_good_match as the "did the memory
  layer answer me" signal. That signal must only fire positive when usable help
  exists. A problem with zero solutions (best_solution null) offers no
  actionable help and must NOT be labeled strong/exact and must NOT, on its
  own, set no_good_match=false.

  Scenario: Zero-solution problem is not a strong match
    Given a problem with solution_count 0 and best_solution null
    When an agent GETs /v1/search?q=error and that problem is the only candidate
    Then its match_quality is not "strong" and not "exact"
    And it is labeled "no_solution" (or carries has_help false)
    And the top-level no_good_match is true

  Scenario: A solution-bearing match keeps the positive signal
    Given a problem with solution_count 1 and a non-null best_solution
    When an agent searches and that problem matches
    Then match_quality may be "strong" or "exact"
    And no_good_match is false

  Scenario: A solution-bearing match outranks a solution-less one
    Given one matching problem has a solution and another has solution_count 0
    When an agent searches a term both match on
    Then no_good_match is false only on account of the solution-bearing problem
    And an agent filtering on match_quality "strong" never receives the solution-less row

  Scenario: Solution-less problem is kept out of the public list until it has help
    Given an agent remembers a description with no solution
    Then the orphan problem is not surfaced as a strong recall hit
    And recall does not present it as if an answer exists

---
```

## Files

- `backend/tests/features/honest-match-labeling.feature` — the Gherkin above, verbatim.
- `backend/tests/unit/test_honest_match_labeling.py` — step implementations / assertions. Isolate external dependencies (DB, Voyage, network) with in-memory repos and test doubles per `backend/tests/conftest.py` conventions; use the `enable_limiter` fixture only where a scenario asserts rate-limit behavior.

## Steps

1. Copy the scenarios above into `honest-match-labeling.feature`.
2. Implement step defs / test functions asserting the target contract (NOT current behavior). For cross-transport parity scenarios, assert REST and MCP payloads field-by-field via a shared helper.
3. Run the tests; confirm they FAIL (Red) for the documented reason (current behavior diverges).

## Verification

```bash
uv run pytest backend/tests/unit/test_honest_match_labeling.py -q   # expect FAIL (Red) before impl
```
