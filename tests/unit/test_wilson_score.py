import pytest

from app.domain.scoring import calculate_wilson_score


def test_wilson_score_is_zero_when_no_votes() -> None:
    assert calculate_wilson_score(0, 0) == 0.0


def test_wilson_score_prefers_large_sample_high_quality() -> None:
    sample_a = calculate_wilson_score(2, 0)
    sample_b = calculate_wilson_score(100, 5)
    sample_c = calculate_wilson_score(50, 10)

    assert sample_b > sample_c > sample_a


@pytest.mark.parametrize(
    ("upvotes", "downvotes", "expected"),
    [
        (2, 0, 0.342),
        (100, 5, 0.892),
        (50, 10, 0.719),
    ],
)
def test_wilson_score_matches_reference_values(
    upvotes: int,
    downvotes: int,
    expected: float,
) -> None:
    score = calculate_wilson_score(upvotes, downvotes)

    assert score == pytest.approx(expected, rel=1e-2)
