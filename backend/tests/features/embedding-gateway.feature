Feature: Embedding providers route through the AI Gateway

  As the agentbook search stack
  I want embedding calls to route through our Cloudflare AI Gateway
    (agentbook-gw) instead of calling provider APIs with bare keys
  So that upstream keys live in the gateway (BYOK), every embed is logged,
    cached where possible, and key rotation needs no redeploy

  Trajectory/ops rationale: the worker's LLM path already runs through
  agentbook-gw; the backend embedding chain was the last bare-key surface.

  Background:
    Given the AI Gateway base URL and auth token are configured
    And the Gateway routes to Cloudflare Workers AI models

  Scenario: Workers AI embeddings route through the gateway
    Given a Cloudflare Workers AI embedding provider is built in Gateway mode
    When an embedding is requested
    Then the request posts to the Cloudflare AI REST /ai/run endpoint
    And uses the @cf/baai/bge-m3 model
    And returns a 1024-dimensional vector
    And carries only account authorization and cf-aig-gateway-id

  Scenario: Gateway mode never sends raw provider credentials
    Given only Cloudflare-hosted Gateway models are configured
    When any Gateway model request is made
    Then no provider API key is present in the request headers
    And only the Cloudflare account authorization and gateway id are sent

  Scenario: Gateway mode does not construct external provider routes
    Given all third-party Gateway provider configurations are removed
    When the production search stack is resolved
    Then the embedding provider is a Cloudflare Workers AI model
    And no external provider route is attempted

  Scenario: Gateway configuration is valid without provider keys
    Given the gateway base URL and auth token are configured
    And all provider API keys are absent
    When production settings are validated
    Then validation does not reject the embedding configuration

  Scenario: Default behavior without gateway config is unchanged
    Given no gateway base URL is configured
    When providers are constructed with direct keys
    Then requests go directly to provider APIs exactly as before

  Scenario: Gateway mode uses only Cloudflare-hosted models
    Given the production Gateway has no third-party provider configurations
    When the application service is composed
    Then the embedding provider is a Cloudflare Workers AI model
    And the reranker is the Cloudflare Workers AI bge-reranker-base model
    And no provider API key is required

  Scenario: Workers AI model supports multi-turn tool calling
    Given the worker uses a Workers AI Gateway model
    When the model is registered
    Then the model advertises function calling support
    And the model context window is at least 24000 tokens

  Scenario: Backend Gateway chat surfaces use a Cloudflare-hosted model
    Given the backend uses the AI Gateway
    When evaluator or synthesis calls are resolved
    Then they use a workers-ai chat model
    And they do not use a removed OpenRouter route

  Scenario: Workers AI model limits stay within Gateway model capacity
    Given the worker uses the default Workers AI Gateway model
    When the model is registered
    Then max_tokens is no greater than 8192
    And the context window is no greater than 131072
