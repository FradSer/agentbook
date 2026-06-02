# Task 003 (contribute-no-silent-failure) — Test (Red)

**type:** test
**theme:** P0-B
**closes:** PR-5, PR-16, PR-18(length-floor)
**depends-on:** [001]

## Goal

Write the failing (Red) BDD tests for the **No silent failure on the contribute write contract** behavior. These tests encode the target contract and MUST fail against current `main` before the paired impl task (003-contribute-no-silent-failure-impl) makes them pass.

## BDD Scenarios (source of truth)

```gherkin
Feature: No silent failure on the contribute write contract

  A memory layer whose entire value is captured fixes must never return success
  while losing a contributed solution. POST /v1/problems with an inline
  solution (or the MCP-vocabulary aliases solution_content / solution_steps)
  must EITHER attach the solution OR reject the request with a 422 that names
  the offending field. It must never return 201 with the solution silently
  dropped (the silent-failure anti-pattern).

  Scenario: Inline solution field is honored, not dropped
    Given an authenticated agent
    When it POSTs /v1/problems with {"description": "...QueuePool limit reached...", "solution": "Increase pool_size..."}
    Then the response is 201
    And GET on the returned problem_id shows solution_count 1
    And the solution content "Increase pool_size..." is present in solution_history

  Scenario: Unknown solution field is rejected with a naming 422 (extra=forbid)
    Given the write contract does not accept an inline solution on this route
    And an authenticated agent POSTs /v1/problems with an unknown "solution" key
    Then the response is 422
    And the error names the field "solution" as unexpected
    And the error advises the two-step path POST /v1/problems/{id}/solutions
    And no problem is created with a silently discarded solution

  Scenario Outline: MCP-vocabulary aliases never silently vanish
    Given an authenticated agent POSTs /v1/problems with the field "<alias>"
    When the route does not honor that alias
    Then the response is 422 naming "<alias>"
    And the response never returns 201 with solution_count 0 for a request that supplied solution content

    Examples:
      | alias            |
      | solution_content |
      | solution_steps   |

  Scenario: Successful problem-only create self-describes the next step
    Given an authenticated agent POSTs /v1/problems with only a description
    Then the 201 body carries solution_count 0
    And the body carries a next-step affordance pointing at POST /v1/problems/{id}/solutions
    So the agent knows the contribution is only half done

  Scenario: Structured-knowledge field shapes are discoverable, not trial-and-error
    Given the OpenAPI schema for SolutionCreateRequest
    Then the verification field documents its inner object shape {command, expected, buggy}
    And the environment field documents that it is an object, not a string
    So a first contribution does not cost three trial-and-error 422s

  Scenario: A too-short solution error states the minimum, like the description error
    Given an authenticated agent POSTs a solution whose content is below the length floor
    When the write contract rejects it with a 422
    Then the error message states the minimum (e.g. "Solution content must be at least 10 characters")
    And it mirrors the description validator's "minimum 20 characters" message
    So the agent self-corrects in one shot instead of guessing the threshold

---
```

## Files

- `backend/tests/features/contribute-no-silent-failure.feature` — the Gherkin above, verbatim.
- `backend/tests/unit/test_contribute_no_silent_failure.py` — step implementations / assertions. Isolate external dependencies (DB, Voyage, network) with in-memory repos and test doubles per `backend/tests/conftest.py` conventions; use the `enable_limiter` fixture only where a scenario asserts rate-limit behavior.

## Steps

1. Copy the scenarios above into `contribute-no-silent-failure.feature`.
2. Implement step defs / test functions asserting the target contract (NOT current behavior). For cross-transport parity scenarios, assert REST and MCP payloads field-by-field via a shared helper.
3. Run the tests; confirm they FAIL (Red) for the documented reason (current behavior diverges).

## Verification

```bash
uv run pytest backend/tests/unit/test_contribute_no_silent_failure.py -q   # expect FAIL (Red) before impl
```
