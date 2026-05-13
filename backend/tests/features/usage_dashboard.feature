Feature: Use-side dashboard exposes flywheel-health metrics

  As an agentbook operator monitoring whether the platform is being used
  I want a single endpoint that aggregates outcome volume, unique reporters,
        verified-vs-observed split, and top problems by outcome count
  So that pre-pilot adoption signal is visible without per-request
        instrumentation

  Background:
    Given the agentbook service uses in-memory repositories
    And the outcomes and problems tables alone feed the dashboard
    And no new write hot path is introduced

  Scenario: Empty corpus returns valid JSON with zero values
    Given no problems and no outcomes have been seeded
    When GET /v1/dashboard/usage is called
    Then the response status is 200
    And every numeric field is 0
    And top_problems_by_outcomes is an empty list

  Scenario: Outcome volume splits by 7-day and 30-day windows
    Given an outcome created 1 day ago
    And an outcome created 8 days ago
    And an outcome created 35 days ago
    When GET /v1/dashboard/usage is called
    Then outcomes.total is 3
    And outcomes.last_7_days is 1
    And outcomes.last_30_days is 2

  Scenario: Unique reporters are deduplicated and windowed
    Given outcomes from 5 distinct reporters across the last 30 days
    And 3 of those reporters were active in the last 7 days
    When GET /v1/dashboard/usage is called
    Then reporters.unique_total is 5
    And reporters.unique_last_7_days is 3
    And reporters.unique_last_30_days is 5

  Scenario: Verified vs observed outcomes are split
    Given 2 outcomes with kind "verified" and 3 with kind "observed"
    When GET /v1/dashboard/usage is called
    Then outcomes.verified_total is 2
    And outcomes.observed_total is 3

  Scenario: Top problems are ranked DESC and limited to 10
    Given 12 approved problems, each with at least one outcome
    When GET /v1/dashboard/usage is called
    Then top_problems_by_outcomes has length 10
    And the list is ordered by outcome_count DESC

  Scenario: Top problems exclude problems with zero outcomes
    Given 2 approved problems with outcomes
    And 3 approved problems with zero outcomes
    When GET /v1/dashboard/usage is called
    Then problems.total_approved is 5
    And problems.with_outcomes is 2
    And problems.with_zero_outcomes is 3
    And top_problems_by_outcomes has length 2

  Scenario: Long problem descriptions are truncated to 80 characters
    Given an approved problem with a 200-character description
    When GET /v1/dashboard/usage is called
    Then that problem's description in top_problems_by_outcomes
         is at most 80 characters
    And it ends with a single Unicode ellipsis when truncated

  Scenario: 80-character descriptions are returned verbatim
    Given an approved problem whose description is exactly 80 characters
    When GET /v1/dashboard/usage is called
    Then that problem's description is returned unchanged
    And it does not end with an ellipsis
