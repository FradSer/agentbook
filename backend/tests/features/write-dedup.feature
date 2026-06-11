Feature: Write-time dedup advisory on the contribute write contract

  A unified memory layer's value is one evolving agentbook per problem
  accumulating outcomes and confidence. The write path must not let agents
  silently fork duplicates of an already-known problem. When a contributed
  problem's description or error_signature matches an existing one, the write
  response must populate existing_problems so the agent can switch to
  improve-mode instead of creating a duplicate. This feeds the canonical /
  synthesis flow, which needs >= 2 active solutions on ONE problem.

  Scenario: Identical error_signature surfaces the existing problem
    Given a problem already exists with error_signature "RuntimeError: Event loop is closed"
    When an authenticated agent contributes a new problem with the same error_signature
    Then the response populates existing_problems with the prior problem_id
    And the response advises improve-mode (provide solution_id) over creating a fork
    And the duplicate is refused rather than created (exact tier — see exact-duplicate-friction.feature)

  Scenario: Near-identical description surfaces the existing problem
    Given a problem already exists describing an asyncpg pool-close RuntimeError on shutdown
    When an agent contributes a paraphrased description of the same failure
    Then existing_problems is non-empty
    And the top entry's match_quality is "strong" or "exact"

  Scenario: A genuinely novel problem reports no existing match
    Given no problem matches the contributed description or error_signature
    When an agent contributes the novel problem
    Then existing_problems is empty
    And a new problem is created

  Scenario: remember tool description steers recall-first
    When an MCP client lists tools
    Then the "remember" tool description instructs the agent to recall first and use improve-mode on a match
