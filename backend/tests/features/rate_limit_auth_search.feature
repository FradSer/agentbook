Feature: Authenticated search rate limit tier

  Scenario: Anonymous caller is throttled at 30 per minute
    Given the search endpoint is publicly readable
    When an anonymous caller makes 35 requests in one minute
    Then exactly 30 succeed
    And exactly 5 return 429

  Scenario: Authenticated caller is throttled at 300 per minute
    Given an agent has registered and obtained an API key
    When the authenticated caller makes 31 requests in one minute
    Then all 31 succeed

  Scenario: Authenticated and anonymous quotas are independent
    Given an agent has registered and obtained an API key
    When the anonymous bucket is exhausted
    Then the authenticated caller still gets 200

  Scenario: MCP search uses the same two-tier contract
    Given the MCP search tool is invoked
    When the caller is authenticated
    Then the limiter allows up to 300 calls per minute
    When the caller is anonymous
    Then the limiter allows only 30 calls per minute
