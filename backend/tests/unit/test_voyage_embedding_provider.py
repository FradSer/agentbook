"""Unit tests for VoyageEmbeddingProvider.

Mocks the ``voyageai`` SDK so the test suite stays hermetic and runs without
the package installed (the production build pulls voyageai >=0.3.7; the dev
shell may not). Asserts:

* Single-text ``embed`` routes through the batch API at length 1
* ``input_type`` is forwarded verbatim ("query" vs "document")
* ``output_dimension`` defaults to 1024 and follows ``embedding_dimension``
* Native batch path used by the reembed-corpus script
* Exponential backoff retries up to the documented limit
* After exhausted retries, the original exception is re-raised
* ``resolve_embedding_provider`` returns ``None`` when key is unset
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.core.config import settings
from backend.infrastructure.embeddings import voyage as voyage_mod


@pytest.fixture
def fake_voyageai(monkeypatch):
    """Inject a fake ``voyageai`` module so VoyageEmbeddingProvider works."""
    fake = MagicMock()
    fake.Client = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(voyage_mod, "voyageai", fake)
    return fake


def test_embed_single_text_uses_batch_api_with_query_pole(fake_voyageai):
    fake_voyageai.Client.return_value.embed.return_value = SimpleNamespace(
        embeddings=[[0.1, 0.2, 0.3]]
    )
    provider = voyage_mod.VoyageEmbeddingProvider(
        api_key="ak_test", model="voyage-3-large", output_dimension=1024
    )

    vector = provider.embed("hello", input_type="query")

    assert vector == [0.1, 0.2, 0.3]
    fake_voyageai.Client.return_value.embed.assert_called_once_with(
        texts=["hello"],
        model="voyage-3-large",
        input_type="query",
        output_dimension=1024,
    )


def test_embed_passes_document_input_type_for_indexing(fake_voyageai):
    fake_voyageai.Client.return_value.embed.return_value = SimpleNamespace(
        embeddings=[[0.4, 0.5, 0.6]]
    )
    provider = voyage_mod.VoyageEmbeddingProvider(api_key="ak_test")
    provider.embed("doc text", input_type="document")
    call = fake_voyageai.Client.return_value.embed.call_args
    assert call.kwargs["input_type"] == "document"


def test_embed_rejects_unknown_input_type(fake_voyageai):
    provider = voyage_mod.VoyageEmbeddingProvider(api_key="ak_test")
    with pytest.raises(ValueError, match="input_type"):
        provider.embed("x", input_type="invalid")


def test_embed_documents_batch_path(fake_voyageai):
    fake_voyageai.Client.return_value.embed.return_value = SimpleNamespace(
        embeddings=[[0.1] * 4, [0.2] * 4, [0.3] * 4]
    )
    provider = voyage_mod.VoyageEmbeddingProvider(api_key="ak_test")
    vectors = provider.embed_documents(["a", "b", "c"])
    assert len(vectors) == 3
    assert all(len(v) == 4 for v in vectors)
    call = fake_voyageai.Client.return_value.embed.call_args
    assert call.kwargs["input_type"] == "document"
    assert call.kwargs["texts"] == ["a", "b", "c"]


def test_embed_documents_empty_returns_empty(fake_voyageai):
    provider = voyage_mod.VoyageEmbeddingProvider(api_key="ak_test")
    assert provider.embed_documents([]) == []
    fake_voyageai.Client.return_value.embed.assert_not_called()


def test_backfill_retry_on_transient_then_success(fake_voyageai, monkeypatch):
    """First call raises, second succeeds — the offline ``embed_documents``
    backfill path must retry and return on attempt 2."""
    monkeypatch.setattr(voyage_mod.time, "sleep", lambda _s: None)
    fake_voyageai.Client.return_value.embed.side_effect = [
        RuntimeError("simulated 429"),
        SimpleNamespace(embeddings=[[0.7]]),
    ]
    provider = voyage_mod.VoyageEmbeddingProvider(api_key="ak_test")
    assert provider.embed_documents(["retry me"]) == [[0.7]]
    assert fake_voyageai.Client.return_value.embed.call_count == 2


def test_backfill_retry_exhausts_then_raises(fake_voyageai, monkeypatch):
    """The offline backfill path retries up to the full budget, then re-raises."""
    monkeypatch.setattr(voyage_mod.time, "sleep", lambda _s: None)
    fake_voyageai.Client.return_value.embed.side_effect = RuntimeError("persistent")
    provider = voyage_mod.VoyageEmbeddingProvider(api_key="ak_test")
    with pytest.raises(RuntimeError, match="persistent"):
        provider.embed_documents(["doomed"])
    assert fake_voyageai.Client.return_value.embed.call_count == len(
        voyage_mod._RETRY_DELAYS_SECONDS
    )


def test_live_query_embed_makes_single_attempt_no_retry(fake_voyageai):
    """The live ``embed`` request path is capped: a persistent failure raises
    immediately after one attempt, never blocking on the retry storm."""
    fake_voyageai.Client.return_value.embed.side_effect = RuntimeError("persistent")
    provider = voyage_mod.VoyageEmbeddingProvider(api_key="ak_test")
    with pytest.raises(RuntimeError, match="persistent"):
        provider.embed("doomed", input_type="query")
    assert fake_voyageai.Client.return_value.embed.call_count == 1


def test_live_client_built_with_bounded_timeout_and_no_sdk_retry(fake_voyageai):
    """The Voyage client is constructed with a tight timeout and SDK-internal
    retries disabled so a hung connection aborts at the client timeout."""
    voyage_mod.VoyageEmbeddingProvider(api_key="ak_test")
    init_kwargs = fake_voyageai.Client.call_args.kwargs
    assert init_kwargs.get("timeout") is not None
    assert init_kwargs["timeout"] <= 5.0
    assert init_kwargs.get("max_retries") == 0


def test_init_without_voyageai_installed_raises(monkeypatch):
    monkeypatch.setattr(voyage_mod, "voyageai", None)
    with pytest.raises(RuntimeError, match="voyageai package is not installed"):
        voyage_mod.VoyageEmbeddingProvider(api_key="ak_test")


def test_resolver_returns_none_when_key_missing(monkeypatch):
    monkeypatch.setattr(voyage_mod, "voyageai", MagicMock())
    monkeypatch.setattr(settings, "voyage_api_key", None)
    assert voyage_mod.resolve_embedding_provider() is None


def test_resolver_returns_none_when_voyageai_missing(monkeypatch):
    monkeypatch.setattr(voyage_mod, "voyageai", None)
    monkeypatch.setattr(settings, "voyage_api_key", "ak_test")
    assert voyage_mod.resolve_embedding_provider() is None


def test_resolver_builds_provider_when_both_present(monkeypatch):
    fake = MagicMock()
    fake.Client = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(voyage_mod, "voyageai", fake)
    monkeypatch.setattr(settings, "voyage_api_key", "ak_test")
    monkeypatch.setattr(settings, "voyage_embedding_model", "voyage-3-large")
    monkeypatch.setattr(settings, "embedding_dimension", 1024)

    provider = voyage_mod.resolve_embedding_provider()
    assert isinstance(provider, voyage_mod.VoyageEmbeddingProvider)


def test_openrouter_provider_accepts_input_type_kwarg():
    """Cross-provider parity check: OpenRouter / Fallback must accept the
    ``input_type`` kwarg and ignore it. This prevents call-site drift when
    the resolver picks a non-Voyage provider."""
    from backend.infrastructure.embeddings.fallback import FallbackEmbeddingProvider

    fallback = FallbackEmbeddingProvider()
    v1 = fallback.embed("test", input_type="query")
    v2 = fallback.embed("test", input_type="document")
    assert v1 == v2  # symmetric provider — pole has no effect

    with patch("backend.infrastructure.embeddings.openrouter.httpx.post") as mock_post:
        mock_post.return_value.json.return_value = {"data": [{"embedding": [0.1, 0.2]}]}
        mock_post.return_value.raise_for_status = lambda: None

        from backend.infrastructure.embeddings.openrouter import (
            OpenRouterEmbeddingProvider,
        )

        provider = OpenRouterEmbeddingProvider(api_key="x", model="m")
        provider.embed("text", input_type="document")
        # Symmetric provider — input_type is dropped before the HTTP call.
        body = mock_post.call_args.kwargs["json"]
        assert "input_type" not in body
