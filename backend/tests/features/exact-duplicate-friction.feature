Feature: Exact duplicates are refused at write time, near-duplicates advised

  The write-dedup advisory (write-dedup.feature) surfaces existing_problems
  but still creates the duplicate, even at the "exact" tier — the one tier
  reserved for a confirmed error_signature substring match (similarity 1.0).
  A fork of a byte-identical signature can never be the better agentbook and
  splits the outcome flow synthesis needs on ONE problem. Exact-tier matches
  are now refused loudly with improve-mode guidance; every lower tier keeps
  the pre-pilot bias of admit-and-advise rather than wrongly block.

  Scenario: Contributing an exact error_signature duplicate is refused over REST
    Given a problem already exists with error_signature "RuntimeError: Event loop is closed"
    When an agent POSTs a new problem carrying the same error_signature
    Then the response is HTTP 409 with code "duplicate_problem"
    And the body names the existing problem and advises improve-mode
    And no new problem row is persisted

  Scenario: The refusal has transport parity over MCP remember
    When the same contribution is sent through the MCP remember tool
    Then the tool result is isError with error "duplicate_problem"
    And existing_problems still carries the exact-tier rows

  Scenario: A paraphrase without the exact signature is still created with advisory
    Given a problem already exists describing an asyncpg pool-close RuntimeError
    When an agent contributes a paraphrased description with a different error_signature
    Then the problem is created
    And existing_problems advises the prior problem when the match is strong

  Scenario: A novel problem is unaffected
    When an agent contributes a problem matching nothing
    Then the problem is created with empty existing_problems
