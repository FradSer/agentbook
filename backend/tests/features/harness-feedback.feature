Feature: Harness feedback channel for the worker

  As the autonomous worker
  I want systemic cross-cutting observations (not per-solution defects)
    surfaced through a worker-gated endpoint
  So that framework-level amendments (skill guidance, MCP tool descriptions)
    can be proposed when behavior signals show systematic misuse — with
    humans confirming any actual amendment through review

  Trajectory-alignment rationale: the three surfaces are weights, harness,
  prompts. Our harness (skills/using-agentbook) and prompts (tool
  descriptions) are static; the report's insight is that systemic failure
  patterns should update the harness, not just individual solutions. This
  endpoint computes the systemic view; the candidate-confirmation gate is
  the human review of any resulting amendment.

  Background:
    Given the agentbook service uses in-memory repositories with a query-event log

  Scenario: A reporting gap is detected and surfaced
    Given organic agents recalled solutions repeatedly (identifiable pairs >= 5)
    And fewer than 30 percent of those pairs ever reported an outcome
    When GET /v1/internal/worker/harness-feedback is called with the worker credential
    Then the response contains an observation of kind "reporting_gap"
    And the observation carries the recall pair count and follow-up share

  Scenario: Healthy reporting produces no gap observation
    Given recall pairs whose follow-up share is at least 30 percent
    When the harness feedback is fetched
    Then no "reporting_gap" observation exists

  Scenario: Hot problems are listed as amendment evidence
    Given problems with organic repeat-query pressure
    When the harness feedback is fetched
    Then hot_problems lists them ordered by repeat_queries DESC
    And each entry carries problem_id, description, and repeat_queries

  Scenario: The endpoint is worker-only
    Given no worker credential
    When GET /v1/internal/worker/harness-feedback is called
    Then the response status is 401 or 403
