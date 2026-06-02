# Task 005 (honest-match-labeling) — Impl (Green)

**type:** impl
**theme:** P1-D
**closes:** PR-14
**depends-on:** [005-honest-match-labeling-test]

## Goal

Make the Red tests from 005-honest-match-labeling-test pass. Demote rows whose `best_solution is None`: cap their `match_quality` to a `no_solution` tier excluded from `_GOOD_MATCH_TIERS` so they no longer suppress `no_good_match`, and add a `has_help: bool` (= best_solution is not None) to each row so an agent can filter without per-row null checks.

Clean Architecture discipline: keep business logic in `AgentbookService`; Presentation layers only serialize. Do NOT bump `confidence.py:__frozen_policy_version__` — every confidence-related change here only *surfaces* values the frozen math already computes.

## BDD Scenarios (target behavior)

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

- `backend/application/service.py`

## Interface contract (signatures only — no implementation bodies)

```python
# Application: post-process search rows (in _search_problems)
_GOOD_MATCH_TIERS = {"exact","strong","pattern"}  # 'no_solution' excluded
# row['has_help'] = row['best_solution'] is not None
# if not row['has_help']: row['match_quality'] = 'no_solution'
```

## Steps

1. Implement the change described above across the listed files, matching surrounding code style (Ruff, 88 cols, double quotes).
2. Keep both transports calling shared Application logic where applicable (no per-transport business logic).
3. Run the paired test file; confirm GREEN. Run `make fast` to confirm no regressions.

## Verification

```bash
uv run pytest backend/tests/unit/test_honest_match_labeling.py -q   # expect PASS (Green)
make fast                                                   # no regressions
```
