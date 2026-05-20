"""Search stack resolver uses Voyage/OpenRouter before Fallback."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.infrastructure.embeddings.fallback import FallbackEmbeddingProvider
from backend.infrastructure.embeddings.openrouter import OpenRouterEmbeddingProvider
from backend.infrastructure.reranking.noop import noop_rerank
from backend.infrastructure.search_stack import resolve_search_stack


def test_resolve_search_stack_prefers_voyage() -> None:
    voyage = MagicMock()
    with (
        patch(
            "backend.infrastructure.embeddings.voyage.resolve_embedding_provider",
            return_value=voyage,
        ),
        patch(
            "backend.infrastructure.embeddings.openrouter.resolve_embedding_provider",
            return_value=None,
        ),
        patch(
            "backend.infrastructure.reranking.resolve_rerank_fn",
            return_value=noop_rerank,
        ),
    ):
        stack = resolve_search_stack()
    assert stack.embedding_provider is voyage
    assert stack.embedding_provider_name == "voyage"
    assert stack.rerank_provider_name == "noop"


def test_resolve_search_stack_openrouter_fallback() -> None:
    or_provider = OpenRouterEmbeddingProvider(api_key="k", model="m")
    with (
        patch(
            "backend.infrastructure.embeddings.voyage.resolve_embedding_provider",
            return_value=None,
        ),
        patch(
            "backend.infrastructure.embeddings.openrouter.resolve_embedding_provider",
            return_value=or_provider,
        ),
        patch(
            "backend.infrastructure.reranking.resolve_rerank_fn",
            return_value=noop_rerank,
        ),
    ):
        stack = resolve_search_stack()
    assert stack.embedding_provider_name == "openrouter"


def test_resolve_search_stack_deterministic_fallback() -> None:
    with (
        patch(
            "backend.infrastructure.embeddings.voyage.resolve_embedding_provider",
            return_value=None,
        ),
        patch(
            "backend.infrastructure.embeddings.openrouter.resolve_embedding_provider",
            return_value=None,
        ),
        patch(
            "backend.infrastructure.reranking.resolve_rerank_fn",
            return_value=noop_rerank,
        ),
    ):
        stack = resolve_search_stack()
    assert isinstance(stack.embedding_provider, FallbackEmbeddingProvider)
    assert stack.embedding_provider_name == "fallback"
