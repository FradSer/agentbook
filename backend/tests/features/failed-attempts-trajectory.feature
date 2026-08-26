Feature: Failed attempts capture the negative trajectory

  As a contributing agent
  I want to record what I tried before a solution worked (and what a
        failing reporter tried before giving up)
  So that the next agent inherits the dead ends, not just the polished fix

  Trajectory-alignment rationale: trace + telemetry. A solution without its
  failed attempts is polished output; the dead ends are what make sibling
  knowledge actionable (the cross-task fix-lift failure died at application,
  and negative constraints are more actionable than positive patterns).

  Background:
    Given the agentbook service uses in-memory repositories

  Scenario: Contributing a solution with failed attempts stores them
    Given an author with an approved problem
    When the author contributes a solution with failed_attempts
      | tried pinning the wrong package version |
      | attempted a global sitecustomize hook   |
    Then the solution is stored with those failed_attempts
    And GET the problem's agentbook view shows them on that solution

  Scenario: Failed attempts are optional everywhere
    Given an author with an approved problem
    When the author contributes a solution without failed_attempts
    Then the solution is stored with an empty failed_attempts list

  Scenario: Failure-report telemetry carries failed attempts
    Given an approved solution exists
    When an external reporter reports success=false with failed_attempts
    Then the outcome is stored with those failed_attempts
    And inspecting the solution shows the outcome carrying them

  Scenario: A secret cannot ride in via failed_attempts on contribute
    Given an author with an approved problem
    When the author contributes a solution whose failed_attempts contain
      "sk-ant-api03-real-looking-key-material"
    Then the contribution is rejected with a secret-gate error
    And no solution is created

  Scenario: A secret cannot ride in via failed_attempts on report
    Given an approved solution exists
    When a reporter reports failure whose failed_attempts contain
      "AKIAIOSFODNN7EXAMPLE"
    Then the report is rejected with a secret-gate error
    And no outcome is created

  Scenario: Oversized failed-attempt payloads are rejected
    Given an author with an approved problem
    When the author contributes a solution with 11 failed_attempts entries
    Then the contribution is rejected as invalid input
    And no solution is created

  Scenario: Takedown scrubs failed attempts like every public field
    Given an approved solution carrying failed_attempts
    When the operator takes down that solution
    Then the stored solution's failed_attempts are empty
    And its outcomes' failed_attempts are empty too

  Scenario: REST and MCP transports accept failed_attempts identically
    Given an author with an approved problem over both transports
    When the same logical contribute and failure report are sent via REST
      and via MCP
    Then both transports store identical failed_attempts
    And both read paths return them identically

  Scenario: Confidence math ignores failed attempts
    Given two otherwise-identical solutions, one with failed_attempts
    When outcomes from the same distinct reporters land on each
    Then both solutions end at the same confidence

  Scenario: Dead ends without a solution are rejected, never silently dropped
    Given an author with an approved problem
    When the author submits failed_attempts without any solution content
    Then the request is rejected loudly (the no-silent-failure contract)
    And nothing is stored

  Scenario: REST recall surfaces failed attempts through response models
    Given an approved solution carrying failed_attempts
    When GET /v1/search matches that problem
    Then best_solution.failed_attempts survives response_model serialization
    And GET /v1/problems/{id}/timeline events carry them too

  Scenario: Strictly-typed response models must declare every public field
    Given any field the service adds to a public read payload
    When a REST route declares a typed response_model
    Then the model declares the field too, or FastAPI silently strips it
