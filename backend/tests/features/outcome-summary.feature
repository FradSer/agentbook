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
