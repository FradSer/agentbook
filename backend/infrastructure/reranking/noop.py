"""Identity-order reranker.

Used in two scenarios:

* No ``VOYAGE_API_KEY`` configured (local dev, CI, anonymous tier ops).
* ``VoyageReranker`` exhausts its token bucket or hits a 429 — it falls back
  to this implementation rather than propagate the failure.

Returning the identity ordering means the search result still surfaces in
``similarity_score`` order from Phase 1, which already eliminates the 27%
high-confidence false positives. Reranker is a precision booster on top of
that, not a correctness dependency.
"""

from __future__ import annotations


def noop_rerank(query: str, candidates: list[str], top_k: int) -> list[int]:
    del query  # unused — this is the identity reranker
    return list(range(min(top_k, len(candidates))))
