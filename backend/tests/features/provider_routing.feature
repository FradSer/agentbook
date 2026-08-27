Feature: Gateway-only model routing

  Production Agentbook AI calls use Cloudflare AI Gateway models. Direct
  provider implementations remain available only for local compatibility.
  Executable coverage lives in backend/tests/unit/test_gateway_all_ai.py and
  backend/tests/unit/test_embedding_gateway.py.

  Scenario: production resolves only Cloudflare Gateway models
    Given the Railway environment has AI_GATEWAY_BASE_URL and AI_GATEWAY_AUTH_TOKEN
    When the backend resolves its AI providers
    Then embeddings and chat use workers-ai model ids
    And no Gemini or OpenRouter provider route is selected

  Scenario: local direct-provider compatibility remains available
    Given no Gateway configuration is set
    When local provider tests construct a direct provider
    Then the direct compatibility path remains available
