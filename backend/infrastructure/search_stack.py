"""Resolve embedding + rerank providers for the search API.

External fix agents (OpenRouter, Cursor, etc.) must not perform retrieval
embeddings themselves. All indexing and ``GET /v1/search`` queries use this
stack on the agentbook server: Voyage → OpenRouter → Fallback, with Voyage
rerank when configured.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from backend.core.config import settings
from backend.domain.services import EmbeddingProvider, RerankFn
from backend.infrastructure.embeddings.fallback import FallbackEmbeddingProvider
from backend.infrastructure.reranking.noop import noop_rerank

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ResolvedSearchStack:
    embedding_provider: EmbeddingProvider
    rerank_fn: RerankFn
    embedding_provider_name: str
    rerank_provider_name: str


def resolve_search_stack() -> ResolvedSearchStack:
    from backend.infrastructure.embeddings.openrouter import (
        OpenRouterEmbeddingProvider,
    )
    from backend.infrastructure.embeddings.openrouter import (
        resolve_embedding_provider as resolve_openrouter_embedding,
    )
    from backend.infrastructure.embeddings.voyage import (
        resolve_embedding_provider as resolve_voyage_embedding,
    )
    from backend.infrastructure.reranking import resolve_rerank_fn

    voyage = resolve_voyage_embedding()
    openrouter = resolve_openrouter_embedding()
    embedding = voyage or openrouter or FallbackEmbeddingProvider()

    if voyage is not None:
        embedding_name = "voyage"
    elif isinstance(embedding, OpenRouterEmbeddingProvider):
        embedding_name = "openrouter"
    else:
        embedding_name = "fallback"

    rerank_fn = resolve_rerank_fn()
    rerank_name = "noop" if rerank_fn is noop_rerank else "voyage"

    logger.info(
        "search-stack embedding=%s rerank=%s",
        embedding_name,
        rerank_name,
    )
    return ResolvedSearchStack(
        embedding_provider=embedding,
        rerank_fn=rerank_fn,
        embedding_provider_name=embedding_name,
        rerank_provider_name=rerank_name,
    )


def warn_if_degraded_search_stack(stack: ResolvedSearchStack) -> None:
    """Log when API keys exist but the resolver still chose Fallback/NoOp."""
    if settings.voyage_api_key and stack.rerank_provider_name == "noop":
        logger.warning(
            "VOYAGE_API_KEY set but reranker is NoOp (disabled or SDK missing)"
        )
    if (settings.voyage_api_key or settings.openrouter_api_key) and (
        stack.embedding_provider_name == "fallback"
    ):
        logger.warning(
            "embedding API keys configured but search stack fell back to "
            "deterministic Fallback — good-arm RAG quality will not match production"
        )
