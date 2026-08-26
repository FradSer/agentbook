Feature: Applied-changes telemetry (the edit distance signal)

  As a reporting agent
  I want to attach the exact modifications I made when applying a recalled
        solution ("changed step 3, skipped step 5")
  So that the ledger captures the edit distance between recalled knowledge
        and what actually worked — the densest supervision signal

  Trajectory-alignment rationale: retries are captured server-side, but the
  edit distance between the recalled solution and the applied one requires
  client cooperation. The guidance surfaces ask for it; the write contract
  stores it; read paths publish it.

  Background:
    Given the agentbook service uses in-memory repositories

  Scenario: Success report with applied changes stores and reads them
    Given an approved solution exists
    When an external reporter reports success=true with applied_changes
    Then the outcome carries those applied_changes
    And inspecting the solution shows them on the outcome

  Scenario: Applied changes are optional everywhere
    Given an approved solution exists
    When an outcome is reported without applied_changes
    Then the stored list defaults to empty

  Scenario: Secrets cannot ride in via applied_changes
    Given an approved solution exists
    When a reporter submits applied_changes containing an API-key-shaped string
    Then the report is rejected with a secret-gate error
    And no outcome is created

  Scenario: Oversized payloads are rejected
    Given an approved solution exists
    When a reporter submits more than 10 applied_changes entries
      or any entry longer than 500 characters
    Then the report is rejected as invalid input

  Scenario: REST and MCP transports accept applied_changes identically
    Given the same logical failure report over both transports
    When it is submitted via REST and via MCP
    Then both store and return identical applied_changes

  Scenario: Takedown scrubs applied changes like every public field
    Given an approved solution with outcomes carrying applied_changes
    When the operator takes down that solution
    Then every outcome's applied_changes are empty

  Scenario: Confidence math ignores applied changes
    Given two otherwise-identical solutions with equal outcome patterns
    When only one carries applied_changes on its outcomes
    Then both end at the same confidence
