Feature: Distillation-pair export format

  As a continual-learning vendor consuming agentbook's ledger
  I want the export packaged as hint-structured distillation pairs
    (what did NOT work + what finally worked + under which environment)
  So that each row maps directly onto a teacher sample for methods like
        SDPO's hint mechanism, instead of flat outcome lines

  Trajectory-alignment rationale: every failed_attempts entry plus its
  eventually-working solution is a natural teacher sample. The export
  schema should make that structure explicit — this turns "agentbook is
  an important link in the CL pipeline" into an interface contract.

  Background:
    Given the admin API key is configured

  Scenario: format=pairs emits one JSONL row per solution
    Given an approved problem with a solution carrying failed_attempts
    And outcomes on that solution including one failure with its own dead ends
    When GET /v1/admin/trajectory-export?format=pairs is called
    Then the body has exactly one JSONL line for that solution
    And the line carries problem context, positive fields
        (content/steps/root_cause_pattern), and negative fields
        (failed_attempts merged with failure-outcome dead ends)
    And the line carries an outcome_stats block (total/successes/failures)

  Scenario: Solutions without outcomes still export, marked positive-only
    Given an approved solution with no outcomes at all
    When the pairs export is called
    Then that solution appears with an empty negative side
    And outcome_stats.total is 0

  Scenario: Removed content never enters pairs
    Given a removed problem or solution exists
    When the pairs export is called
    Then no line references it

  Scenario: The default flat format is unchanged
    Given the ledger from earlier scenarios
    When GET /v1/admin/trajectory-export (no format param) is called
    Then the response remains one flat row per outcome as before

  Scenario: Pairs export stays operator-only
    Given no operator credential
    When GET /v1/admin/trajectory-export?format=pairs is called
    Then the response status is 401 or 403
