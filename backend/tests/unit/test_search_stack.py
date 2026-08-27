"""Search stack resolver uses Cloudflare Workers AI in Gateway mode."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.infrastructure.embeddings.fallback import FallbackEmbeddingProvider
from backend.infrastructure.search_stack import resolve_search_stack

_WORKERS_AI_RESOLVER = (
    "backend.infrastructure.embeddings.workers_ai.resolve_embedding_provider"
)
_RERANK_RESOLVER = "backend.infrastructure.reranking.resolve_rerank_fn"


def test_gateway_search_stack_uses_workers_ai() -> None:
    workers_ai = MagicMock()
    with (
        patch(
            "backend.infrastructure.search_stack.settings.ai_gateway_base_url",
            "gateway",
        ),
        patch(_WORKERS_AI_RESOLVER, return_value=workers_ai),
        patch(_RERANK_RESOLVER, return_value=lambda *_: []),
    ):
        stack = resolve_search_stack()
    assert stack.embedding_provider is workers_ai
    assert stack.embedding_provider_name == "workers-ai"


def test_gateway_search_stack_falls_back_deterministically() -> None:
    with (
        patch(
            "backend.infrastructure.search_stack.settings.ai_gateway_base_url",
            "gateway",
        ),
        patch(_WORKERS_AI_RESOLVER, return_value=None),
        patch(_RERANK_RESOLVER, return_value=lambda *_: []),
    ):
        stack = resolve_search_stack()
    assert isinstance(stack.embedding_provider, FallbackEmbeddingProvider)
    assert stack.embedding_provider_name == "fallback"


def test_local_search_stack_keeps_direct_provider_compatibility() -> None:
    voyage = MagicMock()
    with (
        patch("backend.infrastructure.search_stack.settings.ai_gateway_base_url", None),
        patch(
            "backend.infrastructure.embeddings.gemini.resolve_embedding_provider",
            return_value=None,
        ),
        patch(
            "backend.infrastructure.embeddings.voyage.resolve_embedding_provider",
            return_value=voyage,
        ),
        patch(
            "backend.infrastructure.embeddings.openrouter.resolve_embedding_provider",
            return_value=None,
        ),
        patch(_RERANK_RESOLVER, return_value=lambda *_: []),
    ):
        stack = resolve_search_stack()
    assert stack.embedding_provider is voyage
    assert stack.embedding_provider_name == "voyage"
