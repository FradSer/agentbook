"""Cross-encoder reranking providers.

The reranker contract is the ``RerankFn`` callable in
``backend.domain.services``. ``noop_rerank`` (identity ordering) is the
default when no Gateway is configured; ``CloudflareReranker`` is used through
Workers AI when the Gateway is configured.

The reranker reorders candidates *within* the same ``match_quality`` tier
established by Phase 1's ``_classify_match_quality``. It can never promote a
``"poor"`` lexical match above a true substring ``"exact"`` match — the
final sort key in ``AgentbookService._search_problems`` is
``(quality_rank, -rerank_score, -similarity_score)``.
"""

from backend.infrastructure.reranking.cloudflare import (
    CloudflareReranker,
    resolve_rerank_fn,
)
from backend.infrastructure.reranking.noop import noop_rerank

__all__ = ["CloudflareReranker", "noop_rerank", "resolve_rerank_fn"]
