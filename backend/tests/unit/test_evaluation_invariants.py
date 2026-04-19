"""Contract tests for the unified evaluation entry point.

These tests verify scoring invariants that must hold regardless of
implementation changes — analogous to autoresearch's immutable prepare.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.application.confidence import (
    _content_quality_score,
    calculate_confidence,
    evaluate_improvement,
    is_content_regression,
)
from backend.domain.models import Outcome, Solution


def _make_solution(**overrides) -> Solution:
    defaults = {
        "problem_id": uuid4(),
        "author_id": uuid4(),
        "content": "Install numpy with pip install numpy in Docker Alpine",
        "steps": [],
        "confidence": 0.3,
        "outcome_count": 0,
    }
    defaults.update(overrides)
    return Solution(**defaults)


def _make_outcome(reporter_id=None, success=True, **overrides) -> Outcome:
    defaults = {
        "solution_id": uuid4(),
        "reporter_id": reporter_id or uuid4(),
        "success": success,
        "weight": 1.0,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Outcome(**defaults)


# evaluate_improvement invariants


def test_content_regression_rejected():
    existing = _make_solution(
        content="Install numpy with apk add musl-dev gcc then pip install numpy in Alpine"
    )
    proposed = _make_solution(content="pip fix")
    accepted, reason = evaluate_improvement(existing, proposed)
    assert not accepted
    assert reason == "content_regression"


def test_content_bloat_rejected():
    existing = _make_solution(
        content="Install numpy with pip install numpy in Docker Alpine",
        confidence=0.5,
        outcome_count=3,
    )
    proposed = _make_solution(
        content="Install numpy with pip install numpy in Docker Alpine " * 10,
        confidence=0.52,
    )
    accepted, reason = evaluate_improvement(existing, proposed)
    assert not accepted
    assert reason == "content_bloat"


def test_cold_start_better_content_accepted():
    existing = _make_solution(
        content="Try fixing the error",
        confidence=0.3,
        outcome_count=0,
    )
    proposed = _make_solution(
        content="Run `pip install numpy` in your Docker container, "
        "then verify with `python -c 'import numpy'`",
        steps=["pip install numpy", "python -c 'import numpy'"],
        confidence=0.3,
        outcome_count=0,
    )
    accepted, reason = evaluate_improvement(existing, proposed)
    assert accepted
    assert reason == "cold_start_better"


def test_cold_start_equal_content_rejected():
    content = "Install numpy with pip in Docker Alpine"
    existing = _make_solution(content=content, confidence=0.3, outcome_count=0)
    proposed = _make_solution(content=content, confidence=0.3, outcome_count=0)
    accepted, reason = evaluate_improvement(existing, proposed)
    assert not accepted
    assert reason == "cold_start_no_improvement"


def test_confidence_improved_accepted():
    existing = _make_solution(confidence=0.5, outcome_count=5)
    proposed = _make_solution(confidence=0.6)
    accepted, reason = evaluate_improvement(existing, proposed)
    assert accepted
    assert reason == "confidence_improved"


def test_simplification_accepted():
    existing = _make_solution(
        content="A" * 100,
        steps=["step1", "step2"],
        confidence=0.5,
        outcome_count=3,
    )
    proposed = _make_solution(
        content="A" * 70,
        steps=["step1", "step2"],
        confidence=0.5,
    )
    accepted, reason = evaluate_improvement(existing, proposed)
    assert accepted
    assert reason == "simplification"


def test_equal_confidence_no_simplification_rejected():
    existing = _make_solution(
        content="Install numpy in Docker",
        confidence=0.5,
        outcome_count=3,
    )
    proposed = _make_solution(
        content="Install numpy in Docker container",
        confidence=0.5,
    )
    accepted, reason = evaluate_improvement(existing, proposed)
    assert not accepted
    assert reason == "no_improvement"


def test_strict_greater_required_not_equal():
    """Strict > is required for hill-climbing, not >=."""
    existing = _make_solution(confidence=0.5, outcome_count=3)
    proposed = _make_solution(confidence=0.5)
    accepted, _ = evaluate_improvement(existing, proposed)
    assert not accepted


# is_content_regression


def test_is_content_regression_true():
    existing = _make_solution(content="A" * 100, steps=["s1", "s2"])
    proposed = _make_solution(content="A" * 40, steps=["s1"])
    assert is_content_regression(existing, proposed)


def test_is_content_regression_false_with_extra_steps():
    existing = _make_solution(content="A" * 100, steps=["s1"])
    proposed = _make_solution(content="A" * 40, steps=["s1", "s2", "s3"])
    assert not is_content_regression(existing, proposed)


# _content_quality_score invariants


def test_content_quality_score_range():
    for content_len in [0, 10, 100, 1000]:
        for step_count in [0, 5, 15]:
            sol = _make_solution(
                content="x" * content_len,
                steps=[f"step{i}" for i in range(step_count)],
            )
            score = _content_quality_score(sol)
            assert 0.0 <= score <= 1.0


def test_content_quality_score_more_steps_higher():
    base = _make_solution(content="Install numpy", steps=[])
    more = _make_solution(content="Install numpy", steps=["step1", "step2"])
    assert _content_quality_score(more) > _content_quality_score(base)


def test_content_quality_score_specificity_markers():
    plain = _make_solution(content="Install the package normally here")
    marked = _make_solution(
        content="Run `$ pip install numpy` then `$ sudo apt update`"
    )
    assert _content_quality_score(marked) > _content_quality_score(plain)


# calculate_confidence invariants


def test_confidence_self_reports_only_returns_baseline():
    author = uuid4()
    outcomes = [_make_outcome(reporter_id=author, success=True) for _ in range(5)]
    assert calculate_confidence(outcomes, author) == 0.3


def test_confidence_external_successes_monotonic():
    author = uuid4()
    scores = []
    for n in range(1, 6):
        outcomes = [_make_outcome(success=True) for _ in range(n)]
        scores.append(calculate_confidence(outcomes, author))
    for i in range(len(scores) - 1):
        assert scores[i + 1] >= scores[i]


def test_confidence_empty_outcomes_baseline():
    assert calculate_confidence([], uuid4()) == 0.3
