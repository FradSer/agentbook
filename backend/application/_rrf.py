"""Reciprocal Rank Fusion for hybrid dense+sparse retrieval.

RRF combines multiple ranked lists into a single ranking by summing
`1 / (k + rank)` across input lists. It is parameter-stable and does not
require score normalization across heterogeneous retrievers.

Reference: Cormack, Clarke, Buettcher (2009) — "Reciprocal Rank Fusion
outperforms Condorcet and individual Rank Learning Methods".
"""

from __future__ import annotations

from uuid import UUID

from backend.domain.models import Problem


def rrf_fuse(
    rankings: list[list[Problem]],
    k: int = 60,
    limit: int = 20,
) -> list[tuple[Problem, float]]:
    """Fuse ranked Problem lists into one (problem, rrf_score) ranking.

    Args:
        rankings: each inner list is a ranking from a single retriever
            (dense, sparse, etc.), highest-relevance first.
        k: RRF damping constant (60 per the reference paper).
        limit: maximum number of fused results to return.

    Items that appear in multiple input lists accumulate their per-list
    contributions, so consensus across retrievers boosts ranking. Returns
    the fused ranking sorted by score descending.
    """
    scores: dict[UUID, float] = {}
    seen: dict[UUID, Problem] = {}
    for ranking in rankings:
        for rank, problem in enumerate(ranking, start=1):
            seen[problem.problem_id] = problem
            scores[problem.problem_id] = scores.get(problem.problem_id, 0.0) + 1.0 / (
                k + rank
            )

    fused = sorted(
        ((seen[pid], score) for pid, score in scores.items()),
        key=lambda item: item[1],
        reverse=True,
    )
    return fused[:limit]
