"""Unit tests for the LLM-based evaluator provider.

The evaluator is one HTTP call to OpenRouter that returns a comparative
score in [0.0, 1.0]. Two failure modes need to be locked in:

1. **Position-bias correction**: when the prompt order is swapped
   internally, the returned score is inverted before being returned.
2. **Crash safety**: any exception path collapses to a neutral 0.5,
   never raises into the caller.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.infrastructure.evaluation.fallback import FallbackEvaluatorProvider
from backend.infrastructure.evaluation.llm_evaluator import (
    LLMEvaluatorProvider,
    resolve_evaluator_provider,
)


def _completed_response(score: float) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"content": json.dumps({"score": score})}}]
    }
    return response


def test_fallback_evaluator_always_returns_neutral_half() -> None:
    score = FallbackEvaluatorProvider().compare("p", "a", "b")
    assert score == 0.5


@pytest.mark.parametrize("raw,clamped", [(-0.5, 0.0), (1.5, 1.0), (0.42, 0.42)])
def test_llm_evaluator_clamps_score_into_unit_interval(
    raw: float, clamped: float
) -> None:
    """Out-of-range LLM scores must be clipped, not propagated."""
    with (
        patch(
            "backend.infrastructure.evaluation.llm_evaluator.random.random",
            return_value=0.99,  # forces no swap
        ),
        patch(
            "backend.infrastructure.evaluation.llm_evaluator.httpx.post",
            return_value=_completed_response(raw),
        ),
    ):
        score = LLMEvaluatorProvider(api_key="k", model="m").compare("p", "a", "b")
    assert score == pytest.approx(clamped)


def test_llm_evaluator_inverts_score_when_presentation_was_swapped() -> None:
    """When B is shown first (position swapped), a returned 0.7 means B is
    *worse* than A from the LLM's perspective, so the caller must see 0.3.
    """
    with (
        patch(
            "backend.infrastructure.evaluation.llm_evaluator.random.random",
            return_value=0.0,  # forces a swap (< 0.5)
        ),
        patch(
            "backend.infrastructure.evaluation.llm_evaluator.httpx.post",
            return_value=_completed_response(0.7),
        ),
    ):
        score = LLMEvaluatorProvider(api_key="k", model="m").compare("p", "a", "b")
    assert score == pytest.approx(0.3)


def test_llm_evaluator_returns_neutral_half_on_http_error() -> None:
    with patch(
        "backend.infrastructure.evaluation.llm_evaluator.httpx.post",
        side_effect=httpx.HTTPError("connection refused"),
    ):
        score = LLMEvaluatorProvider(api_key="k", model="m").compare("p", "a", "b")
    assert score == 0.5


def test_llm_evaluator_returns_neutral_half_on_malformed_json() -> None:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"content": "this is not json"}}]
    }
    with patch(
        "backend.infrastructure.evaluation.llm_evaluator.httpx.post",
        return_value=response,
    ):
        score = LLMEvaluatorProvider(api_key="k", model="m").compare("p", "a", "b")
    assert score == 0.5


def test_llm_evaluator_returns_neutral_half_on_missing_score_field() -> None:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"content": json.dumps({"reason": "tie"})}}]
    }
    with patch(
        "backend.infrastructure.evaluation.llm_evaluator.httpx.post",
        return_value=response,
    ):
        score = LLMEvaluatorProvider(api_key="k", model="m").compare("p", "a", "b")
    assert score == 0.5


def test_resolve_evaluator_provider_returns_none_without_api_key() -> None:
    # Default test settings have openrouter_api_key=None (see conftest).
    assert resolve_evaluator_provider() is None


def test_resolve_evaluator_provider_returns_provider_when_api_key_set() -> None:
    from backend.core.config import settings

    original = settings.openrouter_api_key
    settings.openrouter_api_key = "test-key"
    try:
        provider = resolve_evaluator_provider()
        assert isinstance(provider, LLMEvaluatorProvider)
    finally:
        settings.openrouter_api_key = original
