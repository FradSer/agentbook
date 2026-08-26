Feature: Embedding provider failover

  As the search API
  I want to try configured embedding providers in priority order at runtime,
    putting failed ones on cooldown and recovering automatically
  So that one expired API key cannot degrade every search to keyword mode
    while a valid provider sits unused

  Trajectory-alignment rationale: production-aligned retrieval is the loop's
  sensory input; a static startup choice that ignores runtime health starves
  it. Prod incident 2026-08-26: Gemini key expired, Voyage key valid, yet
  every search ran keyword-only because the resolver had picked Gemini once.

  Background:
    Given multiple embedding providers are configured

  Scenario: First provider failure fails over within the same request
    Given providers ordered gemini -> voyage -> openrouter
    And gemini raises on embed
    When an embedding is requested
    Then voyage serves the vector
    And no exception escapes to the caller

  Scenario: Failed providers enter a cooldown and recover after it
    Given gemini failed once and voyage served instead
    When another embedding is requested within the cooldown window
    Then gemini is not retried before the cooldown elapses
    And voyage serves directly again

  Scenario: A recovered provider becomes active again
    Given gemini failed once and its cooldown has elapsed
    And gemini now succeeds on embed
    When an embedding is requested
    Then gemini serves again as the active provider

  Scenario: All providers failing raises instead of returning junk
    Given every configured provider raises on embed
    When an embedding is requested
    Then a RuntimeError names the exhausted chain

  Scenario: Single-provider stacks keep their identity
    Given only gemini resolves
    When the search stack resolves
    Then embedding_provider is the gemini instance itself
    And the name stays "gemini"

  Scenario: Multi-provider stacks expose the chain order
    Given gemini, voyage, and openrouter all resolve
    When the search stack resolves
    Then the embedding provider is a failover chain in that priority order
