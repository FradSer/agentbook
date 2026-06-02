# Task 003 (contribute-no-silent-failure) — Impl (Green)

**type:** impl
**theme:** P0-B
**closes:** PR-5, PR-16, PR-18(length-floor)
**depends-on:** [003-contribute-no-silent-failure-test]

## Goal

Make the Red tests from 003-contribute-no-silent-failure-test pass. Eliminate the silent-drop on `POST /v1/problems`: add `model_config = ConfigDict(extra="forbid")` to the write request models, and honor an inline solution by routing `create_problem` to `service.contribute(...)` when solution content is present (returning `solution_id` + a next-step affordance otherwise). Add `Field(description=, examples=)` mirroring the MCP inline shapes (PR-16) and state the minimum in the too-short solution error (PR-18 length-floor leg, `gate.py`).

Clean Architecture discipline: keep business logic in `AgentbookService`; Presentation layers only serialize. Do NOT bump `confidence.py:__frozen_policy_version__` — every confidence-related change here only *surfaces* values the frozen math already computes.

## BDD Scenarios (target behavior)

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

- `backend/presentation/api/routes/problems.py`
- `backend/presentation/api/schemas.py`
- `backend/application/service.py`
- `backend/application/gate.py`

## Interface contract (signatures only — no implementation bodies)

```python
# Presentation: write models reject unknown fields; create accepts an optional inline solution
class ProblemCreateRequest(BaseModel):  # backend/presentation/api/schemas.py
    model_config = ConfigDict(extra="forbid")
    description: str = Field(..., min_length=20, max_length=10000)
    error_signature: str | None = None
    environment: dict | None = Field(default=None, examples=[{"os":"linux","language":"python"}])
    tags: list[str] | None = None
    solution_content: str | None = None
    solution_steps: list[str] | None = None
    root_cause_pattern: str | None = None
    localization_cues: list[str] | None = None
    verification: list[dict] | None = Field(default=None, examples=[[{"command":"pytest -k x","expected":"pass","buggy":"fail"}]])
```

## Steps

1. Implement the change described above across the listed files, matching surrounding code style (Ruff, 88 cols, double quotes).
2. Keep both transports calling shared Application logic where applicable (no per-transport business logic).
3. Run the paired test file; confirm GREEN. Run `make fast` to confirm no regressions.

## Verification

```bash
uv run pytest backend/tests/unit/test_contribute_no_silent_failure.py -q   # expect PASS (Green)
make fast                                                   # no regressions
```
