Feature: Misconfiguration fails loud at boot

  Voyage outputs 1024-dim vectors; the legacy column is vector(1536).
  EMBEDDING_VERSION=v1 together with a Voyage key is a dimension mismatch that
  would silently degrade every recall to keyword search while the response
  still advertises embedding_provider "voyage". This must fail loud, not
  silently degrade.

  Scenario: v1 plus a Voyage key refuses to boot
    Given EMBEDDING_VERSION is "v1"
    And VOYAGE_API_KEY is set
    When create_app() runs validate_production_settings()
    Then boot is refused with a surfaced error naming the dimension mismatch (1024 vs 1536)

  Scenario: Provider field reflects the per-query mechanism, not boot config
    Given the service has fallen back to a keyword scan for a query
    When the response is built
    Then embedding_provider reflects the actual mechanism (e.g. "keyword" or null), not "voyage"
    And it agrees with search_mode "in_memory_scan" / "no_match"

  Scenario: A consistent v2 / Voyage config boots cleanly
    Given EMBEDDING_VERSION is "v2"
    And VOYAGE_API_KEY is set
    When create_app() runs
    Then boot succeeds

---
