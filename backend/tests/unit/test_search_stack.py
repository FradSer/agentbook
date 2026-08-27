"""Search stack resolver uses Cloudflare Workers AI models."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.infrastructure.embeddings.fallback import FallbackEmbeddingProvider
from backend.infrastructure.search_stack import resolve_search_stack

_WORKERS_AI_RESOLVER = (
    "backend.infrastructure.embeddings.workers_ai.resolve_embedding_provider"
)


def test_search_stack_uses_workers_ai() -> None:
    workers_ai = MagicMock()
    with patch(_WORKERS_AI_RESOLVER, return_value=workers_ai):
        stack = resolve_search_stack()
    assert stack.embedding_provider is workers_ai
    assert stack.embedding_provider_name == "workers-ai"


def test_search_stack_falls_back_deterministically() -> None:
    with patch(_WORKERS_AI_RESOLVER, return_value=None):
        stack = resolve_search_stack()
    assert isinstance(stack.embedding_provider, FallbackEmbeddingProvider)
    assert stack.embedding_provider_name == "fallback"
