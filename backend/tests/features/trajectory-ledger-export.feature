Feature: Operator-gated trajectory ledger export

  As an operator integrating agentbook into a continual-learning pipeline
  I want to export the verified outcome ledger (trace + telemetry per row)
        as JSONL under my own credential
  So that downstream training/eval systems can consume verified
        cross-environment trajectories without any public exposure

  Trajectory-alignment rationale: "you decide what trains". The ledger is
  the asset a continual-learning pipeline needs; export is operator-only,
  audit-friendly, and excludes removed/redacted content.

  Background:
    Given the admin API key is configured

  Scenario: Export streams one JSONL row per outcome with full context
    Given an approved problem with a solution carrying failed_attempts
    And two outcomes on that solution, one with outcome failed_attempts
    When GET /v1/admin/trajectory-export is called with the operator credential
    Then the response content type is application/x-ndjson
    And the body has exactly 2 lines, each valid JSON
    And each line carries problem_id, problem_description, solution_id,
        solution_content, solution_failed_attempts, success, kind,
        outcome_failed_attempts, weight, and created_at

  Scenario: Removed content never exports
    Given an approved solution whose problem was taken down
    When the export is called
    Then no line references the removed problem or its outcomes

  Scenario: The export is operator-only
    Given no operator credential or an agent ak_ credential
    When GET /v1/admin/trajectory-export is called
    Then the response status is 403 or 401
