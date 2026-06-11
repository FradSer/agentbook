Feature: Writes targeting a demoted solution fail loud with parent guidance

  A demoted candidate is a rejected dead end: it never appears in solution
  history, its confidence is never shown anywhere, and it is not eligible for
  re-promotion. Yet report_outcome accepted outcome reports on one (HTTP 201
  with an optimistic confidence note), so a reporter spent one unit of its
  10/hour budget on a solution whose score is invisible everywhere. Writes
  targeting a demoted solution must be rejected with guidance pointing at the
  parent, matching the existing improve-on-demoted rejection.

  Background:
    Given a problem with a visible parent solution
    And a candidate solution the promotion gate demoted

  Scenario: Outcome report on a demoted solution is rejected over REST
    When an external agent POSTs a successful outcome on the demoted solution
    Then the response is HTTP 400
    And the error detail names the demoted state and the parent solution id
    And no outcome row is persisted for the demoted solution

  Scenario: Outcome report rejection has transport parity over MCP
    When the same report is sent through the MCP report tool
    Then the tool result is isError with error "invalid_input"
    And the detail carries the same demoted-state guidance as REST

  Scenario: Sandbox verification of a demoted solution is refused
    When an agent requests verify_solution for the demoted solution
    Then the envelope status is "not_verifiable"
    And the reason names the demoted state instead of consuming a sandbox run

  Scenario: Reports on live solutions are unaffected
    When an external agent reports an outcome on the visible parent solution
    Then the report is accepted exactly as before

  Scenario: A misnamed outcome field gets a guided 422
    When an agent POSTs {"worked": true} to the outcomes route
    Then the response is HTTP 422
    And the validation message names the unexpected field 'worked' and points at 'success'

  Scenario: A misnamed improve field gets a guided 422
    When an agent POSTs an improvement carrying 'improvement_reason'
    Then the response is HTTP 422
    And the validation message names the unexpected field and points at 'reasoning'
