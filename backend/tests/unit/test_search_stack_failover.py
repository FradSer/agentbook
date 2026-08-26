"""Runtime failover across configured embedding providers.

Prod incident 2026-08-26: the Gemini key expired (API_KEY_INVALID) while the
Voyage key remained valid, but ``resolve_search_stack`` had statically picked
Gemini — so every search degraded to keyword mode and the only working
provider was never tried. The resolver now wraps multi-provider stacks in a
failover chain; single-provider stacks keep their exact identity and name.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.infrastructure.embeddings.failover import FailoverEmbeddingProvider
from backend.infrastructure.embeddings.openrouter import OpenRouterEmbeddingProvider
from backend.infrastructure.reranking.noop import noop_rerank
from backend.infrastructure.search_stack import resolve_search_stack

_GEMINI_RESOLVER = "backend.infrastructure.embeddings.gemini.resolve_embedding_provider"


def _patch_all(gemini, voyage, openrouter):
    return (
        patch(_GEMINI_RESOLVER, return_value=gemini),
        patch(
            "backend.infrastructure.embeddings.voyage.resolve_embedding_provider",
            return_value=voyage,
        ),
        patch(
            "backend.infrastructure.embeddings.openrouter.resolve_embedding_provider",
            return_value=openrouter,
        ),
        patch(
            "backend.infrastructure.reranking.resolve_rerank_fn",
            return_value=noop_rerank,
        ),
    )


def test_single_provider_stack_keeps_identity_and_name() -> None:
    gemini = MagicMock()
    patches = _patch_all(gemini, None, None)
    with patches[0], patches[1], patches[2], patches[3]:
        stack = resolve_search_stack()
    assert stack.embedding_provider is gemini
    assert stack.embedding_provider_name == "gemini"


def test_multi_provider_stack_wraps_failover_chain_in_priority_order() -> None:
    gemini, voyage, openrouter = MagicMock(), MagicMock(), MagicMock()
    patches = _patch_all(gemini, voyage, openrouter)
    with patches[0], patches[1], patches[2], patches[3]:
        stack = resolve_search_stack()
    chain = stack.embedding_provider
    assert isinstance(chain, FailoverEmbeddingProvider)
    assert chain.name_chain == "gemini>voyage>openrouter"
    assert stack.embedding_provider_name == "gemini>voyage>openrouter"
    assert stack.rerank_provider_name == "noop"


def test_two_provider_stack_names_both_entries() -> None:
    voyage = MagicMock()
    openrouter = OpenRouterEmbeddingProvider(api_key="k", model="m")
    patches = _patch_all(None, voyage, openrouter)
    with patches[0], patches[1], patches[2], patches[3]:
        stack = resolve_search_stack()
    assert stack.embedding_provider_name == "voyage>openrouter"
