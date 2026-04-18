"""Red tests for evaluate_improvement sandbox-primary dispatch.

When a problem has ``error_signature`` and sandbox is available, the
sandbox verdict is decisive. Sandbox unavailable or missing
``error_signature`` falls back to the legacy Bayesian tree.
"""

from __future__ import annotations

from uuid import uuid4

from backend.application.confidence import evaluate_improvement
from backend.domain.models import Solution


def _sol(
    *, confidence: float, content: str, steps: int, outcome_count: int = 0
) -> Solution:
    return Solution(
        problem_id=uuid4(),
        author_id=uuid4(),
        content=content,
        steps=["step"] * steps,
        confidence=confidence,
        outcome_count=outcome_count,
    )


def test_sandbox_pass_flips_acceptance_vs_lower_bayesian() -> None:
    existing = _sol(confidence=0.72, content="old fix content " * 10, steps=2)
    proposed = _sol(confidence=0.55, content="new fix content " * 10, steps=2)

    accepted, reason = evaluate_improvement(
        existing,
        proposed,
        sandbox_score=1.0,
        problem_has_error_signature=True,
        sandbox_available=True,
    )

    assert accepted is True
    assert reason == "sandbox_verified_pass"


def test_sandbox_unavailable_falls_back_to_bayesian() -> None:
    existing = _sol(
        confidence=0.60, content="old content " * 10, steps=2, outcome_count=5
    )
    proposed = _sol(
        confidence=0.80, content="new content " * 10, steps=2, outcome_count=5
    )

    accepted, reason = evaluate_improvement(
        existing,
        proposed,
        sandbox_score=None,  # provider unavailable
        problem_has_error_signature=True,
        sandbox_available=False,
    )

    assert accepted is True
    assert reason == "confidence_improved"


def test_no_error_signature_never_uses_sandbox_branch() -> None:
    existing = _sol(confidence=0.50, content="old " * 20, steps=2, outcome_count=5)
    proposed = _sol(confidence=0.70, content="new " * 20, steps=2, outcome_count=5)

    # sandbox_score supplied but problem_has_error_signature=False.
    accepted, reason = evaluate_improvement(
        existing,
        proposed,
        sandbox_score=1.0,
        problem_has_error_signature=False,
        sandbox_available=True,
    )

    # Bayesian branch runs; reason is NOT any sandbox_* reason.
    assert accepted is True
    assert reason == "confidence_improved"
    assert "sandbox" not in reason


def test_sandbox_fail_rejects_regardless_of_evaluator_score() -> None:
    existing = _sol(confidence=0.40, content="old " * 20, steps=2, outcome_count=0)
    proposed = _sol(confidence=0.40, content="new " * 20, steps=2, outcome_count=0)

    accepted, reason = evaluate_improvement(
        existing,
        proposed,
        evaluator_score=0.92,  # LLM thinks proposed is much better
        sandbox_score=0.0,  # sandbox verdict: proposed fails
        problem_has_error_signature=True,
        sandbox_available=True,
    )

    assert accepted is False
    assert reason == "sandbox_verified_fail"


def test_sandbox_tie_falls_back_to_simplicity_rule() -> None:
    # Both pass sandbox. Proposed is shorter + same steps -> simplification win.
    existing = _sol(confidence=0.40, content="x" * 200, steps=2, outcome_count=0)
    proposed = _sol(confidence=0.40, content="x" * 100, steps=2, outcome_count=0)

    accepted, reason = evaluate_improvement(
        existing,
        proposed,
        sandbox_score=0.6,  # tie-signal: both passed, proposed slightly preferred
        problem_has_error_signature=True,
        sandbox_available=True,
    )

    assert accepted is True
    assert reason == "sandbox_tied_simplification"
