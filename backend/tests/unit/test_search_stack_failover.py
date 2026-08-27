"""Runtime failover across configured Gateway embedding providers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.infrastructure.embeddings.failover import FailoverEmbeddingProvider
from backend.infrastructure.reranking.noop import noop_rerank
from backend.infrastructure.search_stack import resolve_search_stack

_WORKERS_AI_RESOLVER = (
    "backend.infrastructure.embeddings.workers_ai.resolve_embedding_provider"
)
_VOYAGE_RESOLVER = "backend.infrastructure.embeddings.voyage.resolve_embedding_provider"
_RERANK_RESOLVER = "backend.infrastructure.reranking.resolve_rerank_fn"


def _patch_all(workers_ai, voyage):
    return (
        patch(
            "backend.infrastructure.search_stack.settings.ai_gateway_base_url",
            "gateway",
        ),
        patch(_WORKERS_AI_RESOLVER, return_value=workers_ai),
        patch(_VOYAGE_RESOLVER, return_value=voyage),
        patch(_RERANK_RESOLVER, return_value=noop_rerank),
    )


def test_single_provider_stack_keeps_identity_and_name() -> None:
    workers_ai = MagicMock()
    patches = _patch_all(workers_ai, None)
    with patches[0], patches[1], patches[2], patches[3]:
        stack = resolve_search_stack()
    assert stack.embedding_provider is workers_ai
    assert stack.embedding_provider_name == "workers-ai"


def test_multi_provider_stack_wraps_failover_chain_in_priority_order() -> None:
    workers_ai, voyage = MagicMock(), MagicMock()
    patches = _patch_all(workers_ai, voyage)
    with patches[0], patches[1], patches[2], patches[3]:
        stack = resolve_search_stack()
    chain = stack.embedding_provider
    assert isinstance(chain, FailoverEmbeddingProvider)
    assert chain.name_chain == "workers-ai>voyage"
    assert stack.embedding_provider_name == "workers-ai>voyage"
    assert stack.rerank_provider_name == "noop"


def test_voyage_is_used_when_workers_ai_is_unavailable() -> None:
    voyage = MagicMock()
    patches = _patch_all(None, voyage)
    with patches[0], patches[1], patches[2], patches[3]:
        stack = resolve_search_stack()
    assert stack.embedding_provider is voyage
    assert stack.embedding_provider_name == "voyage"
