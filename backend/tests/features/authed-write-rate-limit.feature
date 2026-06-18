Feature: Authenticated write verbs are rate-limited per author

  Reads are throttled (REST search via slowapi, MCP recall via its own limiter)
  and outcome reports are capped at 10/hour, but the authenticated write verbs —
  create problem, create solution, and improve — had no bound, so a single valid
  key could flood the public CC0 commons unbounded. Each author gets a per-hour
  contribution budget; the content gate and confidence math remain the other
  layers, but the volume itself must be bounded.

  Scenario: An author that exceeds the hourly write budget is throttled
    Given the write rate limiter is enabled with a small budget
    When one author contributes up to the budget
    Then each contribution within the budget is accepted
    But the next contribution from that author is rejected as rate-limited

  Scenario: The budget is per author, not global
    Given the write rate limiter is enabled with a small budget
    And one author has exhausted its budget
    When a different author contributes
    Then that contribution is accepted
