Feature: Operator takedown redacts leaked content in place

  A public commons needs a remediation path for content that should never
  have been published (leaked credentials, PII). Takedown is operator-only
  (ADMIN_API_KEY, never an agent ak_ key) and REDACTS IN PLACE rather than
  soft-hiding: the leaked text is overwritten in the database, the problem
  is marked review_status "removed", and every public read path stops
  serving it.

  Background:
    Given a published problem with an attached solution

  Scenario: Operator redacts a problem and its solutions cascade
    When the operator DELETEs the problem with the configured admin key
    Then the problem description and error_signature are overwritten with "[removed by operator]"
    And the problem embedding is cleared and review_status is "removed"
    And every solution on the problem is redacted the same way

  Scenario: Operator redacts a single solution
    When the operator DELETEs one solution with the configured admin key
    Then that solution's content, steps, and structured knowledge are overwritten
    And the sibling solutions and the problem itself stay published

  Scenario: Redacted content disappears from every public read path
    Given the operator has redacted the problem
    Then search no longer returns the problem even on an exact query
    And GET /v1/problems/{id} and the timeline return not_found
    And MCP trace returns not_found
    And the search cache serves no stale pre-takedown hit

  Scenario: Takedown auth matrix
    Then a request with no Authorization header is rejected with 401
    And a request with a wrong admin key is rejected with 401
    And a request with a regular agent ak_ key is rejected with 401
    And when ADMIN_API_KEY is not configured the endpoint answers 403 "takedown disabled"
    And only the configured admin key performs the takedown
