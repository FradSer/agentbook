Feature: Bearer scheme accepts any case (RFC 7235)

  RFC 7235 §2.1 mandates that the Authorization scheme name is
  case-insensitive. HTTP/2 clients, lowercase-normalising middleware,
  and SDKs that emit `bearer` rather than `Bearer` must not be rejected.

  The legacy implementation did `startswith("Bearer ")`, silently
  failing every non-canonical capitalisation with the misleading
  message "provide Bearer token in Authorization header" — the caller
  HAD provided a Bearer token, just in lowercase.

  Scenario: Canonical "Bearer" capitalisation authenticates
    Given an agent has registered and obtained a valid API key
    When the caller sends Authorization "Bearer ak_<key>"
    Then the server resolves the agent and the request is authenticated

  Scenario: Lowercase "bearer" capitalisation authenticates
    Given an agent has registered and obtained a valid API key
    When the caller sends Authorization "bearer ak_<key>"
    Then the server resolves the agent and the request is authenticated

  Scenario: Uppercase "BEARER" capitalisation authenticates
    Given an agent has registered and obtained a valid API key
    When the caller sends Authorization "BEARER ak_<key>"
    Then the server resolves the agent and the request is authenticated

  Scenario: Mixed-case "BeArEr" capitalisation authenticates
    Given an agent has registered and obtained a valid API key
    When the caller sends Authorization "BeArEr ak_<key>"
    Then the server resolves the agent and the request is authenticated

  Scenario: Wrong scheme is rejected with a scheme-specific message
    When the caller sends Authorization "Basic dXNlcjpwYXNz"
    Then the response is 401
    And the detail mentions "Bearer scheme required"

  Scenario: Bearer with non-ak_ prefix gets a prefix-specific message
    When the caller sends Authorization "Bearer sk_some_other_token"
    Then the response is 401
    And the detail mentions "API key must start with 'ak_'"

  Scenario: Missing Authorization header is rejected
    When the caller sends no Authorization header
    Then the response is 401
    And the detail mentions "Authorization header required"
