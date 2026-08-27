"""Cross-encoder reranking providers.

The reranker contract is the ``RerankFn`` callable in
``backend.domain.services``. ``noop_rerank`` (identity ordering) is the
default for local development; ``VoyageReranker`` is used through the
Cloudflare AI Gateway when configured.

The reranker reorders candidates *within* the same ``match_quality`` tier
established by Phase 1's ``_classify_match_quality``. It can never promote a
``"poor"`` lexical match above a true substring ``"exact"`` match — the
final sort key in ``AgentbookService._search_problems`` is
``(quality_rank, -rerank_score, -similarity_score)``.
"""

from backend.infrastructure.reranking.noop import noop_rerank
from backend.infrastructure.reranking.voyage import (
    VoyageReranker,
    resolve_rerank_fn,
)

__all__ = ["VoyageReranker", "noop_rerank", "resolve_rerank_fn"]
