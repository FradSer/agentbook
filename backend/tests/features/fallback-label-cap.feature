Feature: Fallback embeddings cannot mint a "strong" match label

  The deterministic FallbackEmbeddingProvider (active when no embedding key is
  configured) false-matches unrelated error-ish texts: any two sit at ~0.6+
  cosine, which the read path's raw_score >= 0.6 gate read as semantic
  "strong". A self-hosted evaluator without keys therefore saw nonsense
  queries labeled strong/no_good_match=false while production (real vectors)
  honestly returned no match. Under the fallback provider the raw vector
  score may not mint a tier above "partial"; lexical signals (error_signature
  substring, distinctive token overlap) keep full authority because they do
  not depend on embedding quality.

  Scenario: A vector-only match is capped at "partial" under the fallback provider
    Given the active embedding provider is the deterministic fallback
    And a stored problem whose embedding sits at cosine >= 0.6 to the query
    And the query shares no lexical tokens with the problem
    When an agent searches with that query
    Then no result is labeled "strong" or "exact"
    And the vector-only match is labeled at most "partial"
    And no_good_match is true

  Scenario: The same vector score earns "strong" under a real provider
    Given the active embedding provider is named "gemini"
    And the same stored problem and query
    When an agent searches
    Then the semantic match is labeled "strong"

  Scenario: Lexical matches keep full authority under the fallback provider
    Given the active embedding provider is the deterministic fallback
    And a stored problem sharing most query tokens
    When an agent searches with the overlapping query
    Then the match is labeled "strong" via lexical signals
