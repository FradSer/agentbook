Feature: MCP tool authentication enforcement

  Public tools (recall, trace) are served without credentials.
  Write tools (remember, report, verify) require a valid API key and
  return an in-band error payload rather than raising an exception, so
  MCP clients receive a well-formed JSON-RPC response in every case.

  Scenario: Anonymous caller invokes remember and receives unauthorized payload
    Given no authenticated agent is present in the MCP context
    When the caller invokes the "remember" tool with a valid description
    Then the response contains error "unauthorized"
    And the detail mentions "Authentication required"
    And no problem is written to the repository

  Scenario: Anonymous caller invokes legacy contribute and receives unauthorized payload
    Given no authenticated agent is present in the MCP context
    When the caller invokes the "contribute" tool with a valid description
    Then the response contains error "unauthorized"
    And the detail mentions "Authentication required"
    And no problem is written to the repository

  Scenario: Anonymous caller invokes report and receives unauthorized payload
    Given no authenticated agent is present in the MCP context
    When the caller invokes the "report" tool with a solution_id and success flag
    Then the response contains error "unauthorized"
    And the detail mentions "Authentication required"
    And no outcome is written to the repository

  Scenario: Anonymous caller invokes verify and receives unauthorized payload
    Given no authenticated agent is present in the MCP context
    When the caller invokes the "verify" tool with a solution_id
    Then the response contains error "unauthorized"
    And the detail mentions "Authentication required"

  Scenario: Authenticated caller invokes remember and write succeeds
    Given a registered agent with a valid API key is present in the MCP context
    When the caller invokes the "remember" tool with a valid description
    Then the response does not contain an error field
    And a new problem is created in the repository

  Scenario: recall and trace work without any credentials
    Given no authenticated agent is present in the MCP context
    When the caller invokes the "recall" tool with a query
    Then the response contains a results array
    When the caller invokes the "trace" tool with a valid problem id
    Then the response contains a type field
