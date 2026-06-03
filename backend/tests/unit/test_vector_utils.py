"""Unit tests for backend.infrastructure.persistence.vector_utils.

This is the cosine-similarity primitive used by the in-memory dense
retriever and the FlexibleVector fallback path on Railway. Drift here
is a silent ranking-quality regression.
"""

from __future__ import annotations

import math

from backend.infrastructure.persistence.vector_utils import cosine_similarity


def test_identical_vectors_score_one() -> None:
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0


def test_opposite_vectors_score_minus_one() -> None:
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0


def test_orthogonal_vectors_score_zero() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_empty_inputs_return_zero_without_crashing() -> None:
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([1.0], []) == 0.0
    assert cosine_similarity([], [1.0]) == 0.0


def test_mismatched_lengths_return_zero() -> None:
    assert cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0]) == 0.0


def test_zero_vector_returns_zero_not_nan() -> None:
    """Division-by-zero guard: a zero vector must not raise nor return NaN."""
    result = cosine_similarity([0.0, 0.0, 0.0], [1.0, 2.0, 3.0])
    assert result == 0.0
    assert not math.isnan(result)


def test_scaling_does_not_change_similarity() -> None:
    base = cosine_similarity([1.0, 2.0, 3.0], [4.0, 5.0, 6.0])
    scaled = cosine_similarity([10.0, 20.0, 30.0], [4.0, 5.0, 6.0])
    assert math.isclose(base, scaled, rel_tol=1e-12)
