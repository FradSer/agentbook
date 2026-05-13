"""Unit tests for the confidence scoring engine (app.application.confidence).

BDD scenarios:

Given no outcomes
When calculate_confidence is called
Then it returns the base confidence 0.3

Given all successes
When calculate_confidence is called
Then confidence is close to 1.0

Given all failures
When calculate_confidence is called
Then confidence is close to 0.0

Given a self-report vs an external report
When calculate_confidence is called
Then self-reports carry lower weight than external reports

Given recent vs old outcomes
When calculate_confidence is called
Then recent outcomes contribute more than old ones

Given outcomes from one reporter vs many reporters
When calculate_confidence is called
Then diversity of reporters increases confidence
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from backend.application.confidence import calculate_confidence
from backend.domain.models import Outcome, utc_now

# Shared fixtures / helpers

AUTHOR_ID = UUID("00000000-0000-0000-0000-000000000001")
SOLUTION_ID = UUID("00000000-0000-0000-0000-000000000002")
EXTERNAL_ID = UUID("00000000-0000-0000-0000-000000000003")


def make_outcome(
    *,
    reporter_id: UUID | None = None,
    success: bool = True,
    weight: float = 1.0,
    days_ago: int = 0,
) -> Outcome:
    """Build an outcome.

    ``reporter_id`` defaults to a fresh ``uuid4()`` so that constructing
    N outcomes without overriding the reporter expresses what these
    tests actually mean — N distinct external reporters. The pre-v6
    default re-used ``EXTERNAL_ID`` for every call, which silently
    became a single-reporter dataset and inflated the score past the
    v6 cold-start floor.
    """
    o = Outcome(
        solution_id=SOLUTION_ID,
        reporter_id=reporter_id if reporter_id is not None else uuid4(),
        success=success,
        weight=weight,
    )
    if days_ago > 0:
        object.__setattr__(o, "created_at", utc_now() - timedelta(days=days_ago))
    return o


# Base cases


def test_no_outcomes_returns_baseline_0_3() -> None:
    """Given no outcomes, confidence is 0.3."""
    result = calculate_confidence([], AUTHOR_ID)
    assert result == pytest.approx(0.3)


def test_all_successes_returns_value_close_to_1() -> None:
    """Given 3 external successes, confidence > 0.9."""
    outcomes = [make_outcome(success=True) for _ in range(3)]
    result = calculate_confidence(outcomes, AUTHOR_ID)
    assert result > 0.9


def test_all_failures_returns_value_close_to_0() -> None:
    """Given 3 external failures, confidence < 0.1."""
    outcomes = [make_outcome(success=False) for _ in range(3)]
    result = calculate_confidence(outcomes, AUTHOR_ID)
    assert result < 0.1


# Self-report weighting


def test_external_single_success_confidence_at_cold_start_floor() -> None:
    """1 external success -> capped at the v6 cold-start floor (0.5).

    Pre-v6 returned ~0.689 here. The cap exists because a single
    reporter (whether genuine or sybil) is not consensus.
    """
    outcomes = [make_outcome(reporter_id=EXTERNAL_ID, success=True)]
    result = calculate_confidence(outcomes, AUTHOR_ID)
    assert result == pytest.approx(0.5, abs=1e-6)


def test_self_report_single_success_confidence_below_half() -> None:
    """1 self-report success -> confidence < 0.5 (self-report weight = 0.5)."""
    outcomes = [make_outcome(reporter_id=AUTHOR_ID, success=True)]
    result = calculate_confidence(outcomes, AUTHOR_ID)
    assert result < 0.5


def test_self_report_carries_less_weight_than_external() -> None:
    """A single external success yields higher confidence than a self-report."""
    external = [make_outcome(reporter_id=EXTERNAL_ID, success=True)]
    self_report = [make_outcome(reporter_id=AUTHOR_ID, success=True)]
    assert calculate_confidence(external, AUTHOR_ID) > calculate_confidence(
        self_report, AUTHOR_ID
    )


# Recency decay


def test_recent_outcomes_decay_less_than_old_outcomes() -> None:
    """3 fresh successes outrank 3 270-day-old successes.

    Three distinct reporters in each batch keep the comparison above
    the v6 cold-start floor so the cap doesn't mask the decay signal.
    """
    recent = [make_outcome(success=True, days_ago=0) for _ in range(3)]
    old = [make_outcome(success=True, days_ago=270) for _ in range(3)]
    assert calculate_confidence(recent, AUTHOR_ID) > calculate_confidence(
        old, AUTHOR_ID
    )


def test_270_day_old_outcome_has_negligible_contribution() -> None:
    """A 270-day-old success should contribute < 5% of its base weight.

    We verify this indirectly: the resulting confidence stays very close to
    the no-outcome baseline (0.3), because the decayed weight is negligible.
    """
    old = [make_outcome(success=True, days_ago=270)]
    result = calculate_confidence(old, AUTHOR_ID)
    # With negligible contribution the score should be near baseline 0.3
    assert result < 0.35


def test_90_day_old_outcomes_apply_exp_minus_1_decay() -> None:
    """3 90-day-old successes still beat baseline but trail 3 fresh successes.

    exp(-1) ≈ 0.368 decay on each outcome's weight. Three distinct
    reporters in both batches keep the comparison above the v6
    cold-start floor.
    """
    outcomes_90d = [make_outcome(success=True, days_ago=90) for _ in range(3)]
    result = calculate_confidence(outcomes_90d, AUTHOR_ID)
    assert result > 0.3
    fresh = calculate_confidence(
        [make_outcome(success=True, days_ago=0) for _ in range(3)],
        AUTHOR_ID,
    )
    assert result < fresh


# Reporter diversity


def test_diverse_reporters_yield_higher_confidence_than_single_reporter() -> None:
    """10 successes from 10 distinct reporters > 10 successes from 1 reporter."""
    single_reporter_id = UUID("00000000-0000-0000-0000-000000000010")
    single_reporter_outcomes = [
        make_outcome(reporter_id=single_reporter_id, success=True) for _ in range(10)
    ]
    diverse_outcomes = [
        make_outcome(reporter_id=uuid4(), success=True) for _ in range(10)
    ]
    assert calculate_confidence(diverse_outcomes, AUTHOR_ID) > calculate_confidence(
        single_reporter_outcomes, AUTHOR_ID
    )


# Concrete BDD scenario numbers


def test_7_successes_3_failures_external_no_decay_approx_0_70() -> None:
    """7 external successes + 3 external failures -> confidence ≈ 0.70 (±0.05)."""
    outcomes = [make_outcome(success=True) for _ in range(7)] + [
        make_outcome(success=False) for _ in range(3)
    ]
    result = calculate_confidence(outcomes, AUTHOR_ID)
    assert result == pytest.approx(0.70, abs=0.05)


def test_8_successes_3_failures_external_approx_0_727() -> None:
    """8 external successes + 3 external failures -> confidence ≈ 0.727 (±0.05)."""
    outcomes = [make_outcome(success=True) for _ in range(8)] + [
        make_outcome(success=False) for _ in range(3)
    ]
    result = calculate_confidence(outcomes, AUTHOR_ID)
    assert result == pytest.approx(0.727, abs=0.05)


def test_7_successes_4_failures_external_approx_0_636() -> None:
    """7 external successes + 4 external failures -> confidence ≈ 0.636 (±0.05)."""
    outcomes = [make_outcome(success=True) for _ in range(7)] + [
        make_outcome(success=False) for _ in range(4)
    ]
    result = calculate_confidence(outcomes, AUTHOR_ID)
    assert result == pytest.approx(0.636, abs=0.05)
