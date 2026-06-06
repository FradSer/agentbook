"""Tests for the Gemini embedding provider.

The google-genai SDK is mocked at the ``Client`` boundary so these run without
network access or a real key; ``types`` is left real so the EmbedContentConfig
is constructed exactly as production would build it.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.infrastructure.embeddings import gemini


def _fake_embed_content(*, model, contents, config):
    # One 2-d vector per input; [3, 4] normalizes to [0.6, 0.8].
    return SimpleNamespace(
        embeddings=[SimpleNamespace(values=[3.0, 4.0]) for _ in contents]
    )


def _provider(keys, *, dimension=2):
    return gemini.GeminiEmbeddingProvider(
        api_keys=keys, model="gemini-embedding-001", output_dimension=dimension
    )


def test_embed_returns_l2_normalized_vector_at_requested_dim():
    with patch.object(gemini.genai, "Client") as mock_client:
        mock_client.return_value.models.embed_content.side_effect = _fake_embed_content
        vec = _provider(["k"]).embed("pool exhausted", input_type="query")

    assert len(vec) == 2
    assert math.isclose(math.sqrt(sum(v * v for v in vec)), 1.0, abs_tol=1e-9)
    assert vec == pytest.approx([0.6, 0.8])


def test_input_type_maps_to_gemini_task_type():
    with patch.object(gemini.genai, "Client") as mock_client:
        embed = mock_client.return_value.models.embed_content
        embed.side_effect = _fake_embed_content
        provider = _provider(["k"])

        provider.embed("q", input_type="query")
        provider.embed("d", input_type="document")

    task_types = [c.kwargs["config"].task_type for c in embed.call_args_list]
    assert task_types == ["RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT"]


def test_invalid_input_type_raises():
    with patch.object(gemini.genai, "Client") as mock_client:
        mock_client.return_value.models.embed_content.side_effect = _fake_embed_content
        with pytest.raises(ValueError, match="input_type"):
            _provider(["k"]).embed("x", input_type="passage")


def test_keys_rotate_round_robin_across_calls():
    # The provider caches one client per key, so rotation is observed by which
    # per-key client handles each call: k1 on calls 1 and 3, k2 on call 2.
    clients: dict[str, MagicMock] = {}

    def _client_factory(*, api_key):
        client = clients.get(api_key)
        if client is None:
            client = MagicMock()
            client.models.embed_content.side_effect = _fake_embed_content
            clients[api_key] = client
        return client

    with patch.object(gemini.genai, "Client", side_effect=_client_factory):
        provider = _provider(["k1", "k2"])
        provider.embed("a")
        provider.embed("b")
        provider.embed("c")

    assert clients["k1"].models.embed_content.call_count == 2
    assert clients["k2"].models.embed_content.call_count == 1


def test_embed_documents_batches_and_normalizes():
    with patch.object(gemini.genai, "Client") as mock_client:
        mock_client.return_value.models.embed_content.side_effect = _fake_embed_content
        vectors = _provider(["k"]).embed_documents(["one", "two", "three"])

    assert len(vectors) == 3
    assert all(len(v) == 2 for v in vectors)
    assert all(
        math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, abs_tol=1e-9)
        for v in vectors
    )


def test_full_dimension_output_is_not_renormalized():
    # At the native 3072 dim Gemini already returns unit vectors; the provider
    # must pass them through untouched (no client-side normalization).
    def _raw(*, model, contents, config):
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=[3.0, 4.0]) for _ in contents]
        )

    with patch.object(gemini.genai, "Client") as mock_client:
        mock_client.return_value.models.embed_content.side_effect = _raw
        vec = _provider(["k"], dimension=gemini._FULL_DIMENSION).embed("x")

    assert vec == [3.0, 4.0]


def test_resolver_returns_none_without_key(monkeypatch):
    monkeypatch.setattr(gemini.settings, "gemini_api_key", None)
    assert gemini.resolve_embedding_provider() is None


def test_resolver_returns_none_when_sdk_missing(monkeypatch):
    monkeypatch.setattr(gemini.settings, "gemini_api_key", "gk-test")
    monkeypatch.setattr(gemini, "genai", None)
    assert gemini.resolve_embedding_provider() is None


def test_resolver_builds_provider_with_settings(monkeypatch):
    monkeypatch.setattr(gemini.settings, "gemini_api_key", "gk-a, gk-b")
    monkeypatch.setattr(
        gemini.settings, "gemini_embedding_model", "gemini-embedding-001"
    )
    monkeypatch.setattr(gemini.settings, "embedding_dimension", 1024)
    with patch.object(gemini.genai, "Client"):
        provider = gemini.resolve_embedding_provider()
    assert isinstance(provider, gemini.GeminiEmbeddingProvider)
    assert provider._output_dimension == 1024
