"""Unit tests for the OpenRouter embedding provider.

These tests mock ``httpx.post`` so the provider's parsing and validation
logic is exercised hermetically.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.infrastructure.embeddings.openrouter import (
    OpenRouterEmbeddingProvider,
    resolve_embedding_provider,
)


def _ok_response(vector: list[float]) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"data": [{"embedding": vector}]}
    return response


def test_provider_parses_embedding_into_floats() -> None:
    with patch(
        "backend.infrastructure.embeddings.openrouter.httpx.post",
        return_value=_ok_response([1, 2, 3]),
    ):
        result = OpenRouterEmbeddingProvider(api_key="k", model="m").embed("hello")
    assert result == [1.0, 2.0, 3.0]
    assert all(isinstance(v, float) for v in result)


def test_provider_sends_authorization_header_and_body() -> None:
    with patch(
        "backend.infrastructure.embeddings.openrouter.httpx.post",
        return_value=_ok_response([0.1]),
    ) as mock_post:
        OpenRouterEmbeddingProvider(api_key="secret", model="emb-1").embed("hi")

    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer secret"
    assert kwargs["json"]["model"] == "emb-1"
    assert kwargs["json"]["input"] == "hi"


def test_provider_raises_on_empty_data_payload() -> None:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"data": []}
    with (
        patch(
            "backend.infrastructure.embeddings.openrouter.httpx.post",
            return_value=response,
        ),
        pytest.raises(ValueError, match="missing data"),
    ):
        OpenRouterEmbeddingProvider(api_key="k", model="m").embed("hello")


def test_provider_raises_on_non_list_embedding() -> None:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"data": [{"embedding": "not-a-list"}]}
    with (
        patch(
            "backend.infrastructure.embeddings.openrouter.httpx.post",
            return_value=response,
        ),
        pytest.raises(ValueError, match="format is invalid"),
    ):
        OpenRouterEmbeddingProvider(api_key="k", model="m").embed("hello")


def test_provider_propagates_http_errors() -> None:
    """Network errors must surface so callers can decide whether to fall
    back to the keyword path. Silent neutralization would corrupt search
    quality without any signal.
    """
    with (
        patch(
            "backend.infrastructure.embeddings.openrouter.httpx.post",
            side_effect=httpx.HTTPError("boom"),
        ),
        pytest.raises(httpx.HTTPError),
    ):
        OpenRouterEmbeddingProvider(api_key="k", model="m").embed("hello")


def test_resolve_embedding_provider_returns_none_without_api_key() -> None:
    # conftest forces openrouter_api_key=None
    assert resolve_embedding_provider() is None


def test_resolve_embedding_provider_returns_instance_when_api_key_set() -> None:
    from backend.core.config import settings

    original = settings.openrouter_api_key
    settings.openrouter_api_key = "ak_test"
    try:
        provider = resolve_embedding_provider()
        assert isinstance(provider, OpenRouterEmbeddingProvider)
    finally:
        settings.openrouter_api_key = original
