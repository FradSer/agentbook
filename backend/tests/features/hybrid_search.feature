Feature: Hybrid search with reciprocal rank fusion

  Scenario: Pure semantic match wins when query has no overlapping tokens
    Given an approved problem about "asyncio event loop crashes"
    And the query embedding is highly similar to that problem
    But the query text shares no tokens with the description
    When find_hybrid is called with both embedding and query text
    Then the problem appears in the fused ranking via the dense leg

  Scenario: Pure lexical match wins for rare token even with no embedding
    Given an approved problem with description "TypeError on json.dumps"
    When find_hybrid is called with a query "json.dumps TypeError"
    And no embedding is available
    Then the problem appears in the fused ranking via the sparse leg

  Scenario: Items appearing in both legs rank above single-leg matches
    Given an approved problem found by both dense and sparse retrievers
    And another approved problem found only by the dense retriever
    When find_hybrid fuses the two rankings
    Then the dual-leg problem outranks the single-leg problem

  Scenario: Pattern-class tag surfaces a cross-task sibling below the dense threshold
    Given an approved problem tagged "pattern:identity-element-fallback" whose text barely matches the query
    When search_problems is called with pattern_class "identity-element-fallback"
    Then that problem is returned with match_quality "pattern"
    And it is absent when the same query carries no pattern_class

  Scenario: RRF ignores unapproved problems
    Given an unapproved problem matching both embedding and query text
    When find_hybrid is called
    Then the unapproved problem is not in the result

  Scenario: Service falls back to keyword scan when hybrid yields nothing
    Given a single approved problem with a description containing the query
    But the embedding provider is unavailable
    When search_problems is called
    Then the keyword fallback returns that problem
