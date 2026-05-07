"""Pure metric functions for the retrieval-quality eval.

Zero external dependencies (uses ``math.log2``); kept private with the
underscore prefix because these helpers are only consumed by
``test_retrieval_quality.py``. If a future PR exposes retrieval metrics
through an admin endpoint, lift this module to
``backend/infrastructure/evaluation/retrieval_metrics.py`` and drop the
underscore.
"""

from __future__ import annotations

import math
from typing import Literal


def recall_at_k(
    result_ids: list[str],
    expected_ids: list[str],
    k: int,
) -> float:
    """Fraction of expected items that appear in top-k results.

    Raises ``ValueError`` when ``expected_ids`` is empty — callers must
    filter out queries whose ``expected_in_top_k`` is 0 (out-of-corpus /
    confusion cases) before invoking this. Silently returning a default
    would hide caller bugs.
    """
    if not expected_ids:
        raise ValueError(
            "recall_at_k requires non-empty expected_ids; "
            "filter expected_in_top_k=0 queries before calling"
        )
    top = set(result_ids[: max(k, 0)])
    hits = top & set(expected_ids)
    return len(hits) / len(expected_ids)


def reciprocal_rank(
    result_ids: list[str],
    expected_ids: list[str],
) -> float:
    """1 / (1-indexed rank of first expected hit). 0.0 if no hit."""
    expected = set(expected_ids)
    for idx, rid in enumerate(result_ids):
        if rid in expected:
            return 1.0 / (idx + 1)
    return 0.0


def ndcg_at_k(
    result_ids: list[str],
    expected_ids: list[str],
    k: int,
    *,
    mode: Literal["binary", "graded"] = "binary",
    grades_by_id: dict[str, int] | None = None,
) -> float:
    """Normalized Discounted Cumulative Gain at k.

    DCG@k = sum_{i=1..k} (2^rel_i - 1) / log2(i + 1)
    IDCG@k = DCG of the ideal ordering of all relevant items, truncated to k.
    nDCG@k = DCG@k / IDCG@k (0.0 when IDCG is 0).

    Modes:
      * ``binary`` — rel = 1 if id in expected_ids else 0
      * ``graded`` — rel = grades_by_id.get(id, 0); ids absent from
        ``grades_by_id`` get 0 even if they technically hit, so callers must
        populate grades for every expected id.
    """
    k = max(k, 0)
    if mode == "graded":
        if grades_by_id is None:
            raise ValueError("graded mode requires grades_by_id")
        relevances = [grades_by_id.get(rid, 0) for rid in result_ids[:k]]
        ideal = sorted(grades_by_id.values(), reverse=True)[:k]
    else:
        expected = set(expected_ids)
        relevances = [1 if rid in expected else 0 for rid in result_ids[:k]]
        ideal = [1] * min(len(expected), k)

    dcg = sum((2**rel - 1) / math.log2(i + 2) for i, rel in enumerate(relevances))
    idcg = sum((2**rel - 1) / math.log2(i + 2) for i, rel in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile. ``p`` in [0, 100]. Empty input returns 0.0."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    idx = int(round((p / 100.0) * (len(s) - 1)))
    return s[max(0, min(len(s) - 1, idx))]


def mean(values: list[float]) -> float:
    """Arithmetic mean; empty input returns 0.0."""
    if not values:
        return 0.0
    return sum(values) / len(values)
