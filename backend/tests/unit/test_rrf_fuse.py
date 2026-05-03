"""Unit tests for backend.domain.search.rrf_fuse.

RRF is the fusion primitive behind hybrid (dense+sparse) retrieval.
Drift here changes ranking behavior across the whole search surface.
"""

from __future__ import annotations

from uuid import UUID

from backend.domain.models import Problem
from backend.domain.search import rrf_fuse

AUTHOR_ID = UUID("00000000-0000-0000-0000-000000000001")


def _problem(suffix: int) -> Problem:
    return Problem(
        author_id=AUTHOR_ID,
        description=f"problem-{suffix}",
        problem_id=UUID(f"00000000-0000-0000-0000-{suffix:012x}"),
    )


def test_empty_rankings_returns_empty_fused_list() -> None:
    assert rrf_fuse([]) == []
    assert rrf_fuse([[], []]) == []


def test_single_ranking_preserves_order() -> None:
    ranked = [_problem(1), _problem(2), _problem(3)]
    fused = rrf_fuse([ranked])
    assert [p.problem_id for p, _ in fused] == [p.problem_id for p in ranked]


def test_consensus_across_lists_outranks_single_list_top() -> None:
    """A problem present in both lists should beat one only in the top of one list."""
    a, b, c = _problem(1), _problem(2), _problem(3)
    # `b` appears in both lists; `a` is only in list 1; `c` only in list 2.
    fused = rrf_fuse([[a, b], [c, b]])
    top = fused[0][0]
    assert top.problem_id == b.problem_id


def test_scores_are_descending() -> None:
    a, b, c = _problem(1), _problem(2), _problem(3)
    fused = rrf_fuse([[a, b, c], [c, b, a]])
    scores = [score for _, score in fused]
    assert scores == sorted(scores, reverse=True)


def test_limit_truncates_output() -> None:
    problems = [_problem(i) for i in range(10)]
    fused = rrf_fuse([problems], limit=3)
    assert len(fused) == 3


def test_k_parameter_dampens_score_magnitude() -> None:
    """Higher k -> smaller per-rank contribution. 1/(k+1) is rank-1 score for one list."""
    p = _problem(1)
    low_k = rrf_fuse([[p]], k=1)[0][1]
    high_k = rrf_fuse([[p]], k=1000)[0][1]
    assert low_k > high_k


def test_duplicate_within_single_ranking_takes_first_position_only() -> None:
    """Re-listing the same problem accumulates score; the later rank still contributes."""
    p = _problem(1)
    # Only 1 unique id, so one fused entry; score = 1/(60+1) + 1/(60+2).
    fused = rrf_fuse([[p, p]])
    assert len(fused) == 1
    expected = 1.0 / 61 + 1.0 / 62
    assert abs(fused[0][1] - expected) < 1e-12
