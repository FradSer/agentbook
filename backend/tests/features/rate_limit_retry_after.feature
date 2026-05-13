Feature: 429 responses tell the client when to retry

  RFC 6585 §4 strongly recommends that 429 responses include a
  ``Retry-After`` header. Without it an automated agent has to guess —
  and a too-short guess immediately re-trips the bucket, locking the
  agent out for the entire window.

  All three rate-limit surfaces in agentbook must include both an
  HTTP ``Retry-After`` header and a structured
  ``error.details.retry_after_seconds`` field:

  - REST endpoints throttled by slowapi (e.g. ``/v1/search``,
    ``/v1/auth/register``)
  - REST handlers raising the domain ``RateLimitError``
  - MCP ``recall`` (which dispatches outside FastAPI and uses the
    in-process sliding-window limiter)

  Scenario: REST /v1/search 429 carries Retry-After
    Given an anonymous caller has exhausted the 30/minute search bucket
    When the caller makes one more request
    Then the response status is 429
    And the response has a "Retry-After" header
    And the header value is a positive integer not greater than 60
    And the JSON body contains "error.details.retry_after_seconds"

  Scenario: REST /v1/auth/register 429 carries Retry-After
    Given an IP has exhausted the 10/hour register bucket
    When the IP attempts to register again
    Then the response status is 429
    And the response has a "Retry-After" header
    And the header value is a positive integer not greater than 3600

  Scenario: MCP recall 429 carries retry_after_seconds in structuredContent
    Given an anonymous caller has exhausted the MCP recall bucket
    When the caller invokes recall again
    Then the JSON payload's "error" is "rate_limit_exceeded"
    And the payload contains a positive integer "retry_after_seconds"
    And the integer is not greater than 60

  Scenario: MCPRateLimiter.retry_after returns the time until the oldest hit ages out
    Given the limiter has 5 hits with a 60-second window
    When the bucket is full
    Then retry_after returns the seconds until the oldest hit ages out
    And the value is between 1 and 60
