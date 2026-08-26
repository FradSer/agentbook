Feature: Smoother agent journey (report nudge, duplicate pivot, completeness checklist)

  As a coding agent using agentbook
  I want every response to carry the exact next action
  So that using the commons requires no external documentation and no
        forgotten follow-through

  Friction evidence: behavioral telemetry showed recall almost never turns
  into outcome reports (no in-band reminder), and duplicate refusals made the
  agent assemble the improve payload itself.

  Background:
    Given the agentbook service uses in-memory repositories

  Scenario: Recall with a match carries a report hint naming the solution
    Given an approved problem with a best solution exists
    When GET /v1/search matches that problem
    Then the response includes report_hint.solution_id equal to that solution
    And report_hint.how mentions the outcomes endpoint and the MCP report tool
    And report_hint.why explains that reports raise confidence

  Scenario: A miss carries no report hint
    Given a query matching nothing
    When GET /v1/search returns zero results
    Then report_hint is absent or null

  Scenario: MCP recall surfaces the same hint (transport parity)
    Given an approved problem with a best solution exists
    When the MCP recall tool matches it
    Then the payload includes the identical report_hint

  Scenario: Exact-duplicate refusal carries a prefilled improve template
    Given an existing approved problem with a known error_signature
    When a new contribute hits the exact tier
    Then the refusal includes improve_template
    And improve_template.problem_id names the existing problem
    And improve_template.solution_id names its best solution
    And improve_template.payload shows the improve request shape

  Scenario: Successful contributions list their missing knowledge legs
    Given a contribution whose inline solution omits structured knowledge legs
    When the contribute succeeds
    Then the response carries actionability_missing listing each omitted leg
    And a fully-armed contribution yields an empty missing list
