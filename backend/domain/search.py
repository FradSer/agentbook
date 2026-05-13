"""Reciprocal Rank Fusion for hybrid dense+sparse retrieval.

RRF combines multiple ranked lists into a single ranking by summing
`1 / (k + rank)` across input lists. It is parameter-stable and does not
require score normalization across heterogeneous retrievers.

Reference: Cormack, Clarke, Buettcher (2009) — "Reciprocal Rank Fusion
outperforms Condorcet and individual Rank Learning Methods".

The ``SearchDiagnostics`` carrier travels alongside hybrid results so
the application layer can derive a ``search_mode`` label for the
response. Without it the historical failure mode — pgvector silently
unavailable on Railway, dense leg returns ``[]``, the in-process
keyword scan recovers a row, calling agents see no signal that quality
just regressed — would still be invisible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from backend.domain.models import Problem

SearchBackend = Literal["postgres", "memory", "unavailable"]
SearchMode = Literal[
    "hybrid",
    "vector_only",
    "lexical_only",
    "signature_match",
    "keyword_fallback",
    "in_memory_scan",
    "no_match",
]


@dataclass(frozen=True, slots=True)
class SearchDiagnostics:
    """How a hybrid retrieval call actually executed.

    ``backend`` distinguishes the SQL-backed repository (``"postgres"``)
    from the test/DEMO_MODE in-process one (``"memory"``). When the
    SQL repo cannot reach pgvector at all (extension missing, dialect
    mismatch) ``backend`` is ``"unavailable"`` so the service can
    classify the response as a degraded mode.
    """

    backend: SearchBackend
    pgvector_available: bool
    dense_hits: int
    sparse_hits: int


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
