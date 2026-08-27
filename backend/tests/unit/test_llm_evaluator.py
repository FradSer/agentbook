"""Unit tests for the Cloudflare Workers AI evaluator provider.

The evaluator makes one Gateway request and returns a comparative score in
[0.0, 1.0]. Two failure modes need to be locked in:

1. **Position-bias correction**: when the prompt order is swapped
   internally, the returned score is inverted before being returned.
2. **Crash safety**: any exception path collapses to a neutral 0.5,
   never raises into the caller.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from backend.infrastructure.evaluation.fallback import FallbackEvaluatorProvider
from backend.infrastructure.evaluation.llm_evaluator import (
    LLMEvaluatorProvider,
    resolve_evaluator_provider,
)

_GATEWAY = "https://gateway.ai.cloudflare.com/v1/acct/agentbook-gw"


def _gateway_provider(response: httpx.Response) -> LLMEvaluatorProvider:
    client = httpx.Client(transport=httpx.MockTransport(lambda _: response))
    return LLMEvaluatorProvider(
        model="workers-ai/@cf/zai-org/glm-4.7-flash",
        base_url=_GATEWAY,
        auth_token="gateway-token",
        http_client=client,
    )


def _completed_response(score: float) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "result": {
                "choices": [{"message": {"content": json.dumps({"score": score})}}]
            }
        },
    )


def test_fallback_evaluator_always_returns_neutral_half() -> None:
    score = FallbackEvaluatorProvider().compare("p", "a", "b")
    assert score == 0.5


@pytest.mark.parametrize("raw,clamped", [(-0.5, 0.0), (1.5, 1.0), (0.42, 0.42)])
def test_llm_evaluator_clamps_score_into_unit_interval(
    raw: float, clamped: float
) -> None:
    """Out-of-range LLM scores must be clipped, not propagated."""
    with patch(
        "backend.infrastructure.evaluation.llm_evaluator.random.random",
        return_value=0.99,  # forces no swap
    ):
        score = _gateway_provider(_completed_response(raw)).compare("p", "a", "b")
    assert score == pytest.approx(clamped)


def test_llm_evaluator_inverts_score_when_presentation_was_swapped() -> None:
    """When B is shown first (position swapped), a returned 0.7 means B is
    *worse* than A from the LLM's perspective, so the caller must see 0.3.
    """
    with patch(
        "backend.infrastructure.evaluation.llm_evaluator.random.random",
        return_value=0.0,  # forces a swap (< 0.5)
    ):
        score = _gateway_provider(_completed_response(0.7)).compare("p", "a", "b")
    assert score == pytest.approx(0.3)


def test_llm_evaluator_returns_neutral_half_on_http_error() -> None:
    def raise_error(_: httpx.Request) -> httpx.Response:
        raise httpx.HTTPError("connection refused")

    client = httpx.Client(transport=httpx.MockTransport(raise_error))
    provider = LLMEvaluatorProvider(
        model="workers-ai/@cf/zai-org/glm-4.7-flash",
        base_url=_GATEWAY,
        auth_token="gateway-token",
        http_client=client,
    )
    assert provider.compare("p", "a", "b") == 0.5


def test_llm_evaluator_returns_neutral_half_on_malformed_json() -> None:
    response = httpx.Response(
        200,
        json={"result": {"choices": [{"message": {"content": "this is not json"}}]}},
    )
    assert _gateway_provider(response).compare("p", "a", "b") == 0.5


def test_llm_evaluator_returns_neutral_half_on_missing_score_field() -> None:
    response = httpx.Response(
        200,
        json={
            "result": {
                "choices": [{"message": {"content": json.dumps({"reason": "tie"})}}]
            }
        },
    )
    assert _gateway_provider(response).compare("p", "a", "b") == 0.5


def test_resolve_evaluator_provider_returns_none_without_gateway() -> None:
    assert resolve_evaluator_provider() is None


def test_resolve_evaluator_provider_uses_workers_ai_gateway(monkeypatch) -> None:
    from backend.core.config import settings

    monkeypatch.setattr(
        settings,
        "ai_gateway_base_url",
        "https://gateway.ai.cloudflare.com/v1/acct/agentbook-gw",
    )
    monkeypatch.setattr(settings, "ai_gateway_auth_token", "gateway-token")
    provider = resolve_evaluator_provider()
    assert isinstance(provider, LLMEvaluatorProvider)
    assert provider._model == "workers-ai/@cf/zai-org/glm-4.7-flash"
    assert provider._url == "https://api.cloudflare.com/client/v4/accounts/acct/ai/run"
