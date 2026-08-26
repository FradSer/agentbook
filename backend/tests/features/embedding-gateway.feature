Feature: Embedding providers route through the AI Gateway

  As the agentbook search stack
  I want embedding calls to route through our Cloudflare AI Gateway
    (agentbook-gw) instead of calling provider APIs with bare keys
  So that upstream keys live in the gateway (BYOK), every embed is logged,
    cached where possible, and key rotation needs no redeploy

  Trajectory/ops rationale: the worker's LLM path already runs through
  agentbook-gw; the backend embedding chain was the last bare-key surface.

  Background:
    Given the embedding gateway base URL and auth token are configured

  Scenario: Voyage routes through the gateway with gateway auth header
    Given a voyage provider built in gateway mode
    When an embedding is requested
    Then the request posts to {gateway}/custom-voyage/v1/embeddings
    And carries only cf-aig-authorization from the configured token
    And does not carry a Voyage provider key

  Scenario: OpenRouter routes through the gateway
    Given an openrouter provider built in gateway mode
    When an embedding is requested
    Then the request posts to {gateway}/custom-openrouter/api/v1/embeddings
    And carries only cf-aig-authorization

  Scenario: Gateway mode never sends raw provider credentials
    Given Voyage, Gemini, and OpenRouter BYOK configs exist in the gateway
    When any provider request is made
    Then no provider API key is present in the request headers
    And only cf-aig-authorization authenticates the gateway

  Scenario: Gemini routes through the gateway native endpoint
    Given a gemini provider built in gateway mode
    When an embedding is requested
    Then the request posts to {gateway}/google-ai-studio/v1beta/models/...
    And carries only cf-aig-authorization

  Scenario: Gateway mode relaxes per-provider key requirements
    Given no VOYAGE/GEMINI keys are set but the gateway is fully configured
    When the resolvers run
    Then all three providers still resolve (BYOK placeholders)

  Scenario: Voyage reranking routes through the gateway
    Given a Voyage reranker built in gateway mode
    When candidates are reranked
    Then the request posts to {gateway}/custom-voyage/v1/rerank
    And carries only cf-aig-authorization

  Scenario: OpenRouter evaluator and synthesizer route through the gateway
    Given the OpenRouter gateway mode is configured
    When evaluator or synthesizer work runs
    Then requests post to {gateway}/custom-openrouter/api/v1/chat/completions
    And no OpenRouter provider key is sent by the application

  Scenario: Gateway configuration is valid without provider keys
    Given the gateway base URL and auth token are configured
    And all provider API keys are absent
    When production settings are validated
    Then validation does not reject the embedding configuration

  Scenario: Default behavior without gateway config is unchanged
    Given no gateway base URL is configured
    When providers are constructed with direct keys
    Then requests go directly to provider APIs exactly as before
