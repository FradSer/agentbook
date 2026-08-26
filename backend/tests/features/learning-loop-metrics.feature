Feature: Learning-loop throughput instrumentation (the meta-metric)

  As an operator of a continual-learning system
  I want metrics that answer "is the learning loop itself turning?"
  So that a silently starved loop cannot hide behind green content metrics

  Reflection rationale: get_metrics measured resolution rate / confidence /
  coverage while the improvement loop had been starved to zero for months.
  A live system must instrument its own throughput: proposals per window,
  accepted vs rejected, the eligible base, how many survive filtering,
  and an explicit starvation flag.

  Background:
    Given the agentbook service uses in-memory repositories

  Scenario: Empty corpus yields a zeroed learning_loop section
    Given no problems and no research cycles
    When GET /v1/dashboard/metrics is called
    Then learning_loop.proposals_last_7d is 0
    And learning_loop.eligible_base is 0
    And learning_loop.starved is false

  Scenario: Research cycles feed proposal throughput windows
    Given one research cycle created 2 days ago with status "improved"
    And two research cycles created 40 days ago
    When the metrics are computed
    Then learning_loop.proposals_last_7d is 1
    And learning_loop.proposals_last_30d is 1
    And learning_loop.accepted_last_30d is 1

  Scenario: Starvation is flagged when eligible candidates never surface
    Given approved problems below the confidence ceiling
    And every one of them is filtered out by stall or pending gates
    When the metrics are computed
    Then learning_loop.eligible_base is greater than 0
    And learning_loop.starved is true

  Scenario: A healthy loop is not flagged
    Given at least one candidate survives filtering
    When the metrics are computed
    Then learning_loop.starved is false

  Scenario: The typed metrics response model carries the section over HTTP
    Given any deployment
    When GET /v1/dashboard/metrics is called over HTTP
    Then the response includes the learning_loop section
    And strictly-typed response models do not silently strip it
