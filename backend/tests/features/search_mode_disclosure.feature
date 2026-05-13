Feature: Search responses disclose how the result was retrieved

  When pgvector is unavailable on production Postgres, the SQLAlchemy
  repository silently returns ``[]`` and the service falls through to
  an in-process keyword scan against ``list_all()``. The response shape
  is identical to a fully-vector-ranked one, so neither the calling
  agent nor monitoring can detect the quality regression.

  ``/v1/search``, MCP ``recall``, and the trace endpoints must include
  a ``search_mode`` string that names which retrieval path actually ran.
  ``/v1/health-metrics`` must surface ``pgvector_available`` so the
  operator can correlate degraded modes with infrastructure state.

  Scenario: DEMO_MODE returns "in_memory_scan"
    Given the backend is started with DEMO_MODE=1
    When a caller GETs /v1/search?q=docker
    Then the response includes search_mode "in_memory_scan"

  Scenario: Postgres + pgvector returns "hybrid" when both legs match
    Given the backend is wired to Postgres with pgvector loaded
    And the corpus has at least one approved problem matching both legs
    When a caller GETs /v1/search?q=<term>
    Then the response includes search_mode "hybrid"

  Scenario: Postgres without pgvector returns "lexical_only"
    Given the backend is wired to Postgres but pgvector is unavailable
    And the dense leg is silently empty
    When a caller GETs /v1/search?q=<term>
    Then the response includes search_mode "lexical_only"

  Scenario: Both legs miss but in-process keyword scan recovers a row
    Given hybrid retrieval returned no candidates
    When the in-process keyword scan finds a substring match in description
    Then the response includes search_mode "keyword_fallback"

  Scenario: Nothing matched anywhere
    Given hybrid, vector, and keyword scans all return empty
    When the caller searches
    Then the response includes search_mode "no_match"

  Scenario: /v1/health-metrics reports pgvector availability
    When the operator GETs /v1/health-metrics
    Then the response contains "pgvector_available" as a boolean
    And contains a "search_backend" string in {postgres, memory}

  Scenario: MCP recall payload also includes search_mode
    When an MCP client invokes recall
    Then the JSON payload includes "search_mode"
