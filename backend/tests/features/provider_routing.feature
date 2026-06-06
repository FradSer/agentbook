Feature: Gemini-first multi-provider routing with key rotation

  Both the agent LLM and the API embedding stack default to Google Gemini,
  keeping OpenRouter and Voyage as ordered fallbacks. A provider credential may
  hold several comma-separated keys, which are rotated round-robin so one
  throttled or revoked key does not sink every request. Executable coverage
  lives in backend/tests/unit/test_agent_llm_routing.py,
  test_gemini_embedding.py, test_provider_keys.py, and test_search_stack.py.

  Scenario: auto LLM selection prefers Gemini
    Given AGENT_LLM_PROVIDER is "auto"
    And GEMINI_API_KEY is set
    When the agent resolves its active LLM provider
    Then the provider is "gemini" ahead of NVIDIA, Cloudflare and OpenRouter
    And the model id is the configured Gemini model, never an OpenRouter slug

  Scenario: embedding stack prefers Gemini
    Given GEMINI_API_KEY is set
    When resolve_search_stack() runs
    Then embedding_provider_name is "gemini"
    And reduced-dimension Gemini vectors are L2-normalized for cosine search

  Scenario: ordered fallback when Gemini is absent
    Given GEMINI_API_KEY is not set
    When resolve_search_stack() runs
    Then it falls through to Voyage, then OpenRouter, then the deterministic Fallback

  Scenario: multiple keys rotate round-robin
    Given GEMINI_API_KEY holds two comma-separated keys
    When the provider is invoked three times
    Then the keys are used in the order key1, key2, key1

  Scenario: Gemini dimension must match the active column
    Given GEMINI_API_KEY is set
    And EMBEDDING_DIMENSION does not match the EMBEDDING_VERSION column width
    When create_app() runs validate_production_settings()
    Then boot is refused with a surfaced error naming EMBEDDING_DIMENSION
