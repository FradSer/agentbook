"""Unit tests for the unified spam/quality gate — app/application/gate.py."""

from __future__ import annotations

import pytest

from backend.application.gate import GateResult, check_spam


def test_gate_result_is_frozen():
    r = GateResult(passed=True, reason=None)
    with pytest.raises((AttributeError, TypeError)):
        r.passed = False  # type: ignore[misc]


def test_problem_passes_basic_rules():
    result = check_spam(
        "ModuleNotFoundError when running pytest in Docker Alpine container",
        content_type="problem",
    )
    assert result.passed is True
    assert result.reason is None


@pytest.mark.parametrize(
    "content",
    [
        "help",
        "",
        "   \n\t  ",
        "https://example.com/some-link",
        "buy cheap hosting at http://spam.example.com",
        "aaaaaaaaaaaaaaaaaaaaa",
    ],
)
def test_problem_rejected_various_invalid_inputs(content: str) -> None:
    result = check_spam(content, content_type="problem")
    assert result.passed is False
    assert result.reason is not None


def test_problem_rejected_too_short_reason_mentions_length():
    result = check_spam("help", content_type="problem")
    assert "short" in result.reason.lower() or "minimum" in result.reason.lower()


def test_solution_rejected_too_short_no_steps():
    result = check_spam("use pip", content_type="solution")
    assert result.passed is False
    # PR-18 length-floor: the message must state the minimum so an agent
    # self-corrects in one shot instead of guessing the threshold.
    assert "at least 10 characters" in result.reason.lower()


def test_solution_with_short_content_and_valid_steps_passes():
    result = check_spam(
        "Fix it:",
        content_type="solution",
        metadata={"steps": ["pip install package", "restart container"]},
    )
    assert result.passed is True


def test_solution_rejected_spam_pattern():
    result = check_spam(
        "buy cheap licenses at http://deals.example.com", content_type="solution"
    )
    assert result.passed is False


@pytest.mark.parametrize(
    "content",
    [
        "click here to solve your problem with this amazing tool",
        "buy now and get the best deal for your software license issue",
    ],
)
def test_spam_phrases_detected(content: str) -> None:
    assert not check_spam(content, content_type="problem").passed
