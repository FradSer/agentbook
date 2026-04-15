Feature: Standardized agent tool error envelope

  Scenario: Tool error returns structured envelope with type and retryability
    Given the API raises AgentToolError(NOT_FOUND, "no such problem", is_retryable=False)
    When a client receives the response
    Then the status code is 404
    And the body contains error.type "NOT_FOUND"
    And the body contains error.is_retryable false
    And the body contains error.message "no such problem"

  Scenario: Upstream timeout is retryable
    Given the API raises AgentToolError(UPSTREAM_TIMEOUT, "embedding provider timed out", is_retryable=True)
    When a client receives the response
    Then the status code is 504
    And the body contains error.is_retryable true

  Scenario: Schema mismatch returns 422
    Given the API raises AgentToolError(SCHEMA_MISMATCH, "expected list of strings", is_retryable=False)
    When a client receives the response
    Then the status code is 422
    And the body contains error.type "SCHEMA_MISMATCH"

  Scenario: Existing HTTPException paths are unaffected
    Given a route raises HTTPException(404, detail="not here")
    When a client receives the response
    Then the body contains "detail" key
    And the body does not contain an error envelope
