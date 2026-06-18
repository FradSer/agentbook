Feature: Improving a solution can refine structured knowledge on both transports

  The service layer's improve_solution accepts root_cause_pattern,
  localization_cues, and verification and threads them onto the new solution
  (inheriting the parent's values when omitted). But the two write transports
  diverged on the improve verb: REST hard-rejected the fields with a 422
  (extra="forbid", fields undeclared) while MCP silently dropped them on a 200 —
  so an agent attaching refined structured knowledge to an improvement either
  got an error or a false success. Both transports must forward the fields on
  improve exactly as they already do on create, so refining structured
  knowledge is a first-class, transport-agnostic operation.

  Scenario: REST improve accepts and forwards refined structured knowledge
    Given an existing base solution on a problem
    When an agent improves it via REST with a new root_cause_pattern, localization_cues, and verification
    Then the request is accepted (not a 422)
    And the improved solution carries the refined structured knowledge

  Scenario: MCP improve forwards refined structured knowledge instead of dropping it
    Given an existing base solution on a problem
    When an agent improves it via the MCP remember tool with refined structured knowledge
    Then the structured-knowledge fields reach improve_solution
    And the improved solution carries the refined structured knowledge

  Scenario: An improvement that omits structured knowledge still inherits the parent's
    Given an existing base solution carrying structured knowledge
    When an agent improves it without restating the structured knowledge
    Then the improved solution inherits the parent's structured knowledge
