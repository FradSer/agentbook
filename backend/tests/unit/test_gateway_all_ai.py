"""Gateway-only contract for every backend AI provider surface."""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx

from backend.core.config import Settings, validate_production_settings
from backend.infrastructure.evaluation.llm_evaluator import LLMEvaluatorProvider
from backend.infrastructure.reranking.voyage import VoyageReranker
from backend.infrastructure.synthesis.book_synthesizer import LLMBookSynthesizer

BASE = "https://gateway.ai.cloudflare.com/v1/acct/agentbook-gw"
TOKEN = "cf-gateway-token"


def _json_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_reranker_gateway_sends_only_gateway_auth() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(url=str(request.url), headers=dict(request.headers))
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "relevance_score": 0.9},
                    {"index": 0, "relevance_score": 0.1},
                ]
            },
        )

    reranker = VoyageReranker(
        api_key=None,
        base_url=f"{BASE}/custom-voyage",
        auth_token=TOKEN,
        http_client=_json_client(handler),
    )
    assert reranker("q", ["a", "b"], 2) == [1, 0]
    assert seen["url"] == f"{BASE}/custom-voyage/v1/rerank"
    assert seen["headers"]["cf-aig-authorization"] == f"Bearer {TOKEN}"
    assert "authorization" not in seen["headers"]


def test_evaluator_gateway_sends_only_gateway_auth() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(url=str(request.url), headers=dict(request.headers))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps({"score": 0.8})}}]},
        )

    with patch(
        "backend.infrastructure.evaluation.llm_evaluator.random.random",
        return_value=0.99,
    ):
        evaluator = LLMEvaluatorProvider(
            api_key=None,
            model="openai/gpt-4.1-mini",
            base_url=f"{BASE}/custom-openrouter",
            auth_token=TOKEN,
            http_client=_json_client(handler),
        )
        assert evaluator.compare("p", "a", "b") == 0.8
    assert seen["url"] == f"{BASE}/custom-openrouter/api/v1/chat/completions"
    assert seen["headers"]["cf-aig-authorization"] == f"Bearer {TOKEN}"
    assert "authorization" not in seen["headers"]


def test_synthesizer_gateway_gateway_auth_only() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(url=str(request.url), headers=dict(request.headers))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "# distilled"}}]},
        )

    synthesizer = LLMBookSynthesizer(
        api_key=None,
        model="openai/gpt-4.1-mini",
        base_url=f"{BASE}/custom-openrouter",
        auth_token=TOKEN,
        http_client=_json_client(handler),
    )
    assert synthesizer.synthesize({"source": "x"}) == "# distilled"
    assert seen["url"] == f"{BASE}/custom-openrouter/api/v1/chat/completions"
    assert seen["headers"]["cf-aig-authorization"] == f"Bearer {TOKEN}"
    assert "authorization" not in seen["headers"]


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
