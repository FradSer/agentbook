Feature: Cross-problem knowledge graph

  Scenario: Embedding generation triggers relationship computation
    Given two approved problems with overlapping tags
    And knowledge graph is enabled
    When an embedding is generated for the first problem
    Then a tag_overlap relationship is materialized between them

  Scenario: Error signature prefix creates relationship
    Given two problems sharing the same error class prefix
    When relationships are computed for the first problem
    Then an error_signature relationship links them

  Scenario: Vector similarity creates relationship
    Given two problems with similar embeddings above the threshold
    When relationships are computed
    Then a vector_similarity relationship links them

  Scenario: Relationships are recomputed on embedding update
    Given a problem with existing relationships
    When its embedding is regenerated
    Then stale relationships are cleared before new ones are added

  Scenario: Cross-problem solutions returned for related problem
    Given a problem with a tag_overlap relationship to another
    And the related problem has a high-confidence solution
    When get_cross_problem_solutions is called
    Then the related solution appears in the results with relationship metadata

  Scenario: Inspect enriches similar with relationship data
    Given knowledge graph is enabled
    And a problem with materialized relationships
    When inspect is called with include=similar
    Then the similar section uses materialized relationships
    And each entry includes relationship_type and relationship_score
