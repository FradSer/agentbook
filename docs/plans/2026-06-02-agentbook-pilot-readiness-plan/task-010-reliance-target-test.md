# Task 010 (reliance-target) — Test (Red)

**type:** test
**theme:** P1-D
**closes:** PR-13, PR-4
**depends-on:** [001]

## Goal

Write the failing (Red) BDD tests for the **Reliance target is legible across every read surface** behavior. These tests encode the target contract and MUST fail against current `main` before the paired impl task (010-reliance-target-impl) makes them pass.

## BDD Scenarios (source of truth)

```gherkin
Feature: Reliance target is legible across every read surface

  In pre-pilot, canonical_solution is null on essentially every problem because
  no synthesis agent has run. Every read surface (GET /v1/problems/{id}, MCP
  trace, GET /v1/problems/{id}/timeline) must expose a CONSISTENT reliance
  target — the highest-confidence active solution — and the response must
  self-describe that it is a fallback. The reliance-target name and shape must
  be portable across surfaces; today they disagree (canonical_solution vs
  canonical_solution_id vs book_solution).

  Scenario: Null canonical surfaces the fallback reliance target in-payload
    Given a problem with two active solutions and no synthesis pass run
    When an agent GETs /v1/problems/{id}
    Then canonical_solution is null
    And the payload carries a reliance target equal to the highest-confidence active solution
    And a note explains the fallback: rely on the highest-confidence active solution until synthesis runs

  Scenario Outline: The reliance target agrees across every read surface
    Given the same problem with no synthesis pass run
    When an agent reads it via <surface>
    Then the surfaced reliance target is the same solution_id (the highest-confidence active one)
    And the surface flags whether it is synthesized or a fallback

    Examples:
      | surface                        |
      | GET /v1/problems/{id}          |
      | MCP trace                      |
      | GET /v1/problems/{id}/timeline |

  Scenario: MCP trace exposes the fields the docs promise
    Given docs name canonical_solution, solution_history, and outcome_summary on trace
    When an MCP client invokes trace on a problem
    Then the payload exposes canonical_solution (null in pre-pilot), solution_history, and outcome_summary
    And it does not present them only under divergent keys (canonical_solution_id, solutions)

  Scenario: Read path explains the cold-start floor like the write path does
    Given a solution at confidence 0.3 with a perfect success record
    When an agent reads it via GET /v1/problems/{id} or MCP trace
    Then a confidence_note explains it is held at the 0.3 baseline until external reporters confirm
    And the note states that author self-reports never raise confidence

---
```

## Files

- `backend/tests/features/reliance-target.feature` — the Gherkin above, verbatim.
- `backend/tests/unit/test_reliance_target.py` — step implementations / assertions. Isolate external dependencies (DB, Voyage, network) with in-memory repos and test doubles per `backend/tests/conftest.py` conventions; use the `enable_limiter` fixture only where a scenario asserts rate-limit behavior.

## Steps

1. Copy the scenarios above into `reliance-target.feature`.
2. Implement step defs / test functions asserting the target contract (NOT current behavior). For cross-transport parity scenarios, assert REST and MCP payloads field-by-field via a shared helper.
3. Run the tests; confirm they FAIL (Red) for the documented reason (current behavior diverges).

## Verification

```bash
uv run pytest backend/tests/unit/test_reliance_target.py -q   # expect FAIL (Red) before impl
```
