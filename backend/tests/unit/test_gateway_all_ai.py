"""Gateway-only contract for every backend AI provider surface."""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx

from backend.core.config import Settings, validate_production_settings
from backend.infrastructure.embeddings.workers_ai import WorkersAIEmbeddingProvider
from backend.infrastructure.evaluation.llm_evaluator import LLMEvaluatorProvider
from backend.infrastructure.reranking.cloudflare import CloudflareReranker
from backend.infrastructure.synthesis.book_synthesizer import LLMBookSynthesizer

BASE = "https://gateway.ai.cloudflare.com/v1/acct/agentbook-gw"
TOKEN = "cf-gateway-token"


def _json_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_workers_ai_embedding_gateway_sends_only_gateway_auth() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(
            url=str(request.url), headers=dict(request.headers), body=request.read()
        )
        return httpx.Response(200, json={"result": {"data": [[0.1, 0.2]]}})

    provider = WorkersAIEmbeddingProvider(
        base_url=BASE,
        auth_token=TOKEN,
        http_client=_json_client(handler),
    )
    assert provider.embed("probe") == [0.1, 0.2]
    assert seen["url"] == "https://api.cloudflare.com/client/v4/accounts/acct/ai/run"
    assert seen["headers"]["authorization"] == f"Bearer {TOKEN}"
    assert seen["headers"]["cf-aig-gateway-id"] == "agentbook-gw"
    assert "x-provider-key" not in seen["headers"]
    assert b"@cf/baai/bge-m3" in seen["body"]


def test_reranker_gateway_sends_only_gateway_auth() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(url=str(request.url), headers=dict(request.headers))
        return httpx.Response(
            200,
            json={
                "result": {
                    "response": [
                        {"id": 1, "score": 0.9},
                        {"id": 0, "score": 0.1},
                    ]
                }
            },
        )

    reranker = CloudflareReranker(
        base_url=BASE,
        auth_token=TOKEN,
        account_id="acct",
        gateway_id="agentbook-gw",
        http_client=_json_client(handler),
    )
    assert reranker("q", ["a", "b"], 2) == [1, 0]
    assert seen["url"] == "https://api.cloudflare.com/client/v4/accounts/acct/ai/run"
    assert seen["headers"]["authorization"] == f"Bearer {TOKEN}"
    assert seen["headers"]["cf-aig-gateway-id"] == "agentbook-gw"
    assert "x-provider-key" not in seen["headers"]


def test_evaluator_gateway_uses_workers_ai_and_only_gateway_auth() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(url=str(request.url), headers=dict(request.headers))
        return httpx.Response(
            200,
            json={
                "result": {
                    "choices": [{"message": {"content": json.dumps({"score": 0.8})}}]
                }
            },
        )

    with patch(
        "backend.infrastructure.evaluation.llm_evaluator.random.random",
        return_value=0.99,
    ):
        evaluator = LLMEvaluatorProvider(
            api_key=None,
            model="workers-ai/@cf/zai-org/glm-4.7-flash",
            base_url=BASE,
            auth_token=TOKEN,
            http_client=_json_client(handler),
        )
        assert evaluator.compare("p", "a", "b") == 0.8
    assert seen["url"] == "https://api.cloudflare.com/client/v4/accounts/acct/ai/run"
    assert seen["headers"]["authorization"] == f"Bearer {TOKEN}"
    assert seen["headers"]["cf-aig-gateway-id"] == "agentbook-gw"
    assert "x-provider-key" not in seen["headers"]


def test_synthesizer_gateway_uses_workers_ai_and_only_gateway_auth() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(url=str(request.url), headers=dict(request.headers))
        return httpx.Response(
            200,
            json={"result": {"choices": [{"message": {"content": "# distilled"}}]}},
        )

    synthesizer = LLMBookSynthesizer(
        api_key=None,
        model="workers-ai/@cf/zai-org/glm-4.7-flash",
        base_url=BASE,
        auth_token=TOKEN,
        http_client=_json_client(handler),
    )
    assert synthesizer.synthesize({"source": "x"}) == "# distilled"
    assert seen["url"] == "https://api.cloudflare.com/client/v4/accounts/acct/ai/run"
    assert seen["headers"]["authorization"] == f"Bearer {TOKEN}"
    assert seen["headers"]["cf-aig-gateway-id"] == "agentbook-gw"
    assert "x-provider-key" not in seen["headers"]


def test_gateway_only_production_config_is_valid() -> None:
    config = Settings(
        debug=False,
        cors_allow_origins="https://agentbook.up.railway.app",
        embedding_version="v2",
        embedding_dimension=1024,
        ai_gateway_base_url=BASE,
        ai_gateway_auth_token=TOKEN,
        gemini_api_key=None,
        voyage_api_key=None,
        openrouter_api_key=None,
    )
    validate_production_settings(config)
