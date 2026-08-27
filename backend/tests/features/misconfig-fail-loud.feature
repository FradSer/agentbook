Feature: Misconfiguration fails loud at boot

  Cloudflare Workers AI embeddings output 1024-dim vectors; the legacy column
  is vector(1536). EMBEDDING_VERSION=v1 would make writes target the wrong
  column and must fail loud, not silently degrade.

  Scenario: v1 refuses to boot with Gateway embeddings
    Given EMBEDDING_VERSION is "v1"
    And AI_GATEWAY_BASE_URL and AI_GATEWAY_AUTH_TOKEN are set
    When create_app() runs validate_production_settings()
    Then boot is refused with a surfaced error naming the dimension mismatch (1024 vs 1536)

  Scenario: Provider field reflects the per-query mechanism, not boot config
    Given the service has fallen back to a keyword scan for a query
    When the response is built
    Then embedding_provider reflects the actual mechanism (e.g. "keyword" or null), not "voyage"
    And it agrees with search_mode "in_memory_scan" / "no_match"

  Scenario: A consistent v2 / Gateway config boots cleanly
    Given EMBEDDING_VERSION is "v2"
    And AI_GATEWAY_BASE_URL and AI_GATEWAY_AUTH_TOKEN are set
    When create_app() runs
    Then boot succeeds

  Scenario: Missing Gateway configuration is rejected on Railway
    Given AI_GATEWAY_BASE_URL is unset
    And DEBUG is false on Railway
    When create_app() runs validate_production_settings()
    Then boot is refused with a surfaced Gateway configuration error

---
