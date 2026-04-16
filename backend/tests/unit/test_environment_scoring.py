"""Unit tests for environment-aware confidence scoring.

Tests normalize_environment(), calculate_environment_scores(), and the
integration with report_outcome() that populates Solution.environment_scores.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from backend.application.confidence import (
    calculate_environment_scores,
    normalize_environment,
)
from backend.domain.models import Outcome

AUTHOR_ID = UUID("00000000-0000-0000-0000-000000000001")
SOLUTION_ID = UUID("00000000-0000-0000-0000-000000000002")
EXTERNAL_A = UUID("00000000-0000-0000-0000-000000000003")
EXTERNAL_B = UUID("00000000-0000-0000-0000-000000000004")


def _make_outcome(
    *,
    reporter_id: UUID = EXTERNAL_A,
    success: bool = True,
    environment: dict | None = None,
) -> Outcome:
    return Outcome(
        solution_id=SOLUTION_ID,
        reporter_id=reporter_id,
        success=success,
        environment=environment,
    )


# ---------------------------------------------------------------------------
# normalize_environment
# ---------------------------------------------------------------------------


class TestNormalizeEnvironment:
    def test_none_returns_unknown(self) -> None:
        assert normalize_environment(None) == "_unknown"

    def test_empty_dict_returns_unknown(self) -> None:
        assert normalize_environment({}) == "_unknown"

    def test_sorted_keys(self) -> None:
        env_a = {"os": "linux", "language": "python"}
        env_b = {"language": "python", "os": "linux"}
        assert normalize_environment(env_a) == normalize_environment(env_b)

    def test_lowercases_values(self) -> None:
        assert normalize_environment({"os": "Linux"}) == normalize_environment(
            {"os": "linux"}
        )

    def test_deterministic(self) -> None:
        env = {"os": "ubuntu", "python": "3.11", "framework": "django"}
        key1 = normalize_environment(env)
        key2 = normalize_environment(env)
        assert key1 == key2
        assert isinstance(key1, str)
        assert len(key1) > 0

    def test_different_envs_different_keys(self) -> None:
        assert normalize_environment({"os": "linux"}) != normalize_environment(
            {"os": "macos"}
        )


# ---------------------------------------------------------------------------
# calculate_environment_scores
# ---------------------------------------------------------------------------


class TestCalculateEnvironmentScores:
    def test_no_outcomes_returns_global_baseline(self) -> None:
        scores = calculate_environment_scores([], AUTHOR_ID)
        assert "_global" in scores
        assert scores["_global"] == pytest.approx(0.3)

    def test_global_always_present(self) -> None:
        outcomes = [
            _make_outcome(environment={"os": "linux"}),
            _make_outcome(reporter_id=EXTERNAL_B, environment={"os": "macos"}),
        ]
        scores = calculate_environment_scores(outcomes, AUTHOR_ID)
        assert "_global" in scores

    def test_groups_by_environment(self) -> None:
        outcomes = [
            _make_outcome(
                reporter_id=EXTERNAL_A, success=True, environment={"os": "linux"}
            ),
            _make_outcome(
                reporter_id=EXTERNAL_B, success=True, environment={"os": "linux"}
            ),
            _make_outcome(
                reporter_id=EXTERNAL_A, success=False, environment={"os": "macos"}
            ),
            _make_outcome(
                reporter_id=EXTERNAL_B, success=False, environment={"os": "macos"}
            ),
        ]
        scores = calculate_environment_scores(outcomes, AUTHOR_ID)
        linux_key = normalize_environment({"os": "linux"})
        macos_key = normalize_environment({"os": "macos"})
        assert linux_key in scores
        assert macos_key in scores
        # Linux: all success, macOS: all failure
        assert scores[linux_key] > scores[macos_key]

    def test_unknown_env_not_in_scores(self) -> None:
        outcomes = [_make_outcome(environment=None)]
        scores = calculate_environment_scores(outcomes, AUTHOR_ID)
        assert "_unknown" not in scores
        assert "_global" in scores

    def test_single_env_matches_global(self) -> None:
        outcomes = [
            _make_outcome(
                reporter_id=EXTERNAL_A, success=True, environment={"os": "linux"}
            ),
            _make_outcome(
                reporter_id=EXTERNAL_B, success=True, environment={"os": "linux"}
            ),
        ]
        scores = calculate_environment_scores(outcomes, AUTHOR_ID)
        linux_key = normalize_environment({"os": "linux"})
        # When all outcomes share the same env, per-env and global are equal.
        assert scores[linux_key] == pytest.approx(scores["_global"])
