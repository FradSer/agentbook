Feature: Cloudflare Workers AI is the only production AI integration

  As the Agentbook production backend
  I want one Cloudflare Workers AI integration
  So that expired provider credentials and fallback routing cannot return
  to production through stale configuration or code.

  Scenario: Production configuration exposes only Gateway model settings
    Given production settings are loaded
    When the AI configuration is inspected
    Then embedding and reranking use Cloudflare Workers AI model ids
    And chat surfaces use the Cloudflare Workers AI model
    And no provider-specific credential setting exists

  Scenario: Production search stack uses only Workers AI adapters
    Given the AI Gateway is configured
    When the production search stack is resolved
    Then the embedding adapter is Workers AI
    And the reranking adapter is Workers AI
    And no direct provider or provider-key adapter is imported

  Scenario: Missing Gateway configuration is rejected in production
    Given production settings have no Gateway base URL or auth token
    When production settings are validated
    Then startup is rejected with a Gateway configuration error

  Scenario: Local deterministic fallback remains an explicit degraded mode
    Given the Gateway is unavailable in a local test
    When the search stack is resolved
    Then the deterministic fallback is reported honestly
    And no external provider is attempted

  Scenario: Workers AI uses the v2 embedding column as its sole runtime store
    Given a problem is persisted with a Workers AI embedding
    When the problem is read back for search
    Then the embedding_v2 column supplies the embedding
    And the legacy embedding column is not read or written by runtime persistence
    And the legacy embedding column remains in the database schema for compatibility
