"""Resolve embedding and rerank providers for the search API."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from backend.core.config import settings
from backend.domain.services import EmbeddingProvider, RerankFn
from backend.infrastructure.embeddings.failover import FailoverEmbeddingProvider
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
    from backend.infrastructure.embeddings.voyage import (
        resolve_embedding_provider as resolve_voyage_embedding,
    )
    from backend.infrastructure.embeddings.workers_ai import (
        resolve_embedding_provider as resolve_workers_ai_embedding,
    )
    from backend.infrastructure.reranking import resolve_rerank_fn

    workers_ai = resolve_workers_ai_embedding()
    if settings.ai_gateway_base_url:
        voyage = resolve_voyage_embedding()
        resolved = [
            (name, provider)
            for name, provider in (("workers-ai", workers_ai), ("voyage", voyage))
            if provider is not None
        ]
    else:
        from backend.infrastructure.embeddings.gemini import (
            resolve_embedding_provider as resolve_gemini_embedding,
        )
        from backend.infrastructure.embeddings.openrouter import (
            resolve_embedding_provider as resolve_openrouter_embedding,
        )

        resolved = [
            (name, provider)
            for name, provider in (
                ("gemini", resolve_gemini_embedding()),
                ("voyage", resolve_voyage_embedding()),
                ("openrouter", resolve_openrouter_embedding()),
            )
            if provider is not None
        ]
    if not resolved:
        embedding: EmbeddingProvider = FallbackEmbeddingProvider()
        embedding_name = "fallback"
    elif len(resolved) == 1:
        embedding = resolved[0][1]
        embedding_name = resolved[0][0]
    else:
        chain = FailoverEmbeddingProvider(resolved)
        embedding = chain
        embedding_name = chain.name_chain

    rerank_fn = resolve_rerank_fn()
    rerank_name = "noop" if rerank_fn is noop_rerank else "voyage"
    logger.info("search-stack embedding=%s rerank=%s", embedding_name, rerank_name)
    return ResolvedSearchStack(
        embedding_provider=embedding,
        rerank_fn=rerank_fn,
        embedding_provider_name=embedding_name,
        rerank_provider_name=rerank_name,
    )


def warn_if_degraded_search_stack(stack: ResolvedSearchStack) -> None:
    """Log when local development has no Gateway embedding provider."""
    if not settings.ai_gateway_base_url and stack.embedding_provider_name == "fallback":
        logger.warning(
            "Cloudflare AI Gateway is unavailable; search stack fell back to "
            "deterministic embeddings"
        )
