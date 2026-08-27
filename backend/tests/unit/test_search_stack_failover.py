"""Search stack uses one Cloudflare Workers AI provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.infrastructure.search_stack import resolve_search_stack

_WORKERS_AI_RESOLVER = (
    "backend.infrastructure.embeddings.workers_ai.resolve_embedding_provider"
)


def test_single_workers_ai_provider_keeps_identity_and_name() -> None:
    workers_ai = MagicMock()
    with patch(_WORKERS_AI_RESOLVER, return_value=workers_ai):
        stack = resolve_search_stack()
    assert stack.embedding_provider is workers_ai
    assert stack.embedding_provider_name == "workers-ai"


def test_missing_workers_ai_uses_deterministic_fallback() -> None:
    with patch(_WORKERS_AI_RESOLVER, return_value=None):
        stack = resolve_search_stack()
    assert stack.embedding_provider_name == "fallback"
