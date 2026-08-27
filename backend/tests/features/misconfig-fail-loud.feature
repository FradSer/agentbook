Feature: Misconfiguration fails loud at boot

  Cloudflare Workers AI embeddings output 1024-dimensional vectors and runtime
  persistence always targets the Workers AI embedding column.


  Scenario: Provider field reflects the per-query mechanism, not boot config
    Given the service has fallen back to a keyword scan for a query
    When the response is built
    Then embedding_provider reflects the actual mechanism (e.g. "keyword" or null), not a dense provider
    And it agrees with search_mode "in_memory_scan" / "no_match"

  Scenario: A valid Gateway config boots cleanly
    Given AI_GATEWAY_BASE_URL and AI_GATEWAY_AUTH_TOKEN are set
    And EMBEDDING_DIMENSION is 1024
    When create_app() runs
    Then boot succeeds

  Scenario: Missing Gateway configuration is rejected on Railway
    Given AI_GATEWAY_BASE_URL is unset
    And DEBUG is false on Railway
    When create_app() runs validate_production_settings()
    Then boot is refused with a surfaced Gateway configuration error

---
