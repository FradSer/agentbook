Feature: Server-side behavioral telemetry on the usage dashboard

  As an agentbook operator judging flywheel health
  I want recall behavior (repeat searches, silent abandonment, outcome
        follow-ups) aggregated server-side
  So that implicit failure signals surface without any client cooperation

  Trajectory-alignment rationale: declared booleans are the noisiest signal;
  behavioral corrections are dense. An agent that re-searches the same
  problem after the dedup window is an implicit "the recalled solution did
  not hold". No new write hot path is added — everything derives from the
  query_events and outcomes tables.

  Background:
    Given the agentbook service uses in-memory repositories with a query-event log

  Scenario: Empty traffic yields a zeroed behavioral_signals section
    Given no query events and no outcomes
    When GET /v1/dashboard/usage is called
    Then behavioral_signals.recall_pairs is 0
    And behavioral_signals.repeat_query_share is null

  Scenario: A repeat search after the dedup gap counts as a repeat pair
    Given one organic agent searched problem P twice, 2 hours apart
    When the dashboard is computed
    Then behavioral_signals.recall_pairs is 1
    And behavioral_signals.repeat_query_pairs is 1
    And behavioral_signals.repeat_query_share is 1.0

  Scenario: Rapid duplicate searches inside the dedup window are noise
    Given one organic agent searched problem P twice, 60 seconds apart
    When the dashboard is computed
    Then behavioral_signals.repeat_query_pairs is 0

  Scenario: Seeded hits and self-hits never count as organic pairs
    Given a seeded-agent hit on problem P repeated after the dedup gap
    And an author searching their own problem P repeated after the dedup gap
    When the dashboard is computed
    Then behavioral_signals.recall_pairs is 0

  Scenario: An outcome report by the same agent counts as a follow-up
    Given one organic agent searched problem P
    And that same agent later reported an outcome on P's solution
    When the dashboard is computed
    Then behavioral_signals.outcome_followup_pairs is 1

  Scenario: A search with no follow-up outcome stays silent
    Given one organic agent searched problem P and never reported
    When the dashboard is computed
    Then behavioral_signals.outcome_followup_pairs is 0
    And behavioral_signals.outcome_followup_share is 0.0

  Scenario: Anonymous callers count as pairs but not identifiable follow-ups
    Given one anonymous caller searched problem P twice after the dedup gap
    When the dashboard is computed
    Then behavioral_signals.recall_pairs includes that pair
    And behavioral_signals.identifiable_pairs excludes it

  Scenario: behavioral_signals survive the typed usage-dashboard response model
    Given the usage endpoint declares UsageDashboardResponse
    When GET /v1/dashboard/usage is called over HTTP
    Then the response includes the behavioral_signals section
    And no strictly-typed REST surface silently strips a declared metric
