# Task 010 (reliance-target) — Impl (Green)

**type:** impl
**theme:** P1-D
**closes:** PR-13, PR-4
**depends-on:** [010-reliance-target-test, 002-transport-read-parity-impl]

## Goal

Make the Red tests from 010-reliance-target-test pass. Promote `_resolve_book_solution` to the single `reliance_target` (canonical_solution if present else highest-confidence active solution_history[0], with `is_synthesized`) emitted on GET problem, MCP trace, timeline, and aligned with search `best_solution`. Add the documented `canonical_solution`/`solution_history`/`outcome_summary` keys to MCP trace (PR-4).

Clean Architecture discipline: keep business logic in `AgentbookService`; Presentation layers only serialize. Do NOT bump `confidence.py:__frozen_policy_version__` — every confidence-related change here only *surfaces* values the frozen math already computes.

## BDD Scenarios (target behavior)

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

- `backend/application/service.py`
- `backend/presentation/api/routes/problems.py`
- `backend/presentation/mcp/tools.py`

## Interface contract (signatures only — no implementation bodies)

```python
# Application: one reliance-target resolver, four surfaces
def _resolve_reliance_target(self, problem_id) -> dict | None: ...  # {solution_id, is_synthesized, <canonical read row>}
```

## Steps

1. Implement the change described above across the listed files, matching surrounding code style (Ruff, 88 cols, double quotes).
2. Keep both transports calling shared Application logic where applicable (no per-transport business logic).
3. Run the paired test file; confirm GREEN. Run `make fast` to confirm no regressions.

## Verification

```bash
uv run pytest backend/tests/unit/test_reliance_target.py -q   # expect PASS (Green)
make fast                                                   # no regressions
```
