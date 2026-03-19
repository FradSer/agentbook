"""Unit tests for the unified spam/quality gate — app/application/gate.py."""
from __future__ import annotations

import pytest


def test_gate_module_importable():
    from app.application.gate import GateResult, check_spam  # noqa: F401


def test_gate_result_is_dataclass_with_passed_and_reason():
    from app.application.gate import GateResult

    r = GateResult(passed=True, reason=None)
    assert r.passed is True
    assert r.reason is None


def test_gate_result_is_frozen():
    from app.application.gate import GateResult

    r = GateResult(passed=True, reason=None)
    with pytest.raises((AttributeError, TypeError)):
        r.passed = False  # type: ignore[misc]


def test_problem_passes_basic_rules():
    from app.application.gate import check_spam

    result = check_spam(
        "ModuleNotFoundError when running pytest in Docker Alpine container",
        content_type="problem",
    )
    assert result.passed is True
    assert result.reason is None


def test_problem_rejected_too_short():
    from app.application.gate import check_spam

    result = check_spam("help", content_type="problem")
    assert result.passed is False
    assert result.reason is not None
    assert "short" in result.reason.lower() or "minimum" in result.reason.lower()


def test_problem_rejected_url_only():
    from app.application.gate import check_spam

    result = check_spam("https://example.com/some-link", content_type="problem")
    assert result.passed is False
    assert result.reason is not None


def test_problem_rejected_spam_pattern_buy_url():
    from app.application.gate import check_spam

    result = check_spam(
        "buy cheap hosting at http://spam.example.com", content_type="problem"
    )
    assert result.passed is False
    assert result.reason is not None


def test_problem_rejected_low_character_diversity():
    from app.application.gate import check_spam

    result = check_spam("aaaaaaaaaaaaaaaaaaaaa", content_type="problem")
    assert result.passed is False
    assert result.reason is not None


def test_problem_rejected_empty_content():
    from app.application.gate import check_spam

    result = check_spam("", content_type="problem")
    assert result.passed is False
    assert result.reason is not None


def test_problem_rejected_whitespace_only():
    from app.application.gate import check_spam

    result = check_spam("   \n\t  ", content_type="problem")
    assert result.passed is False
    assert result.reason is not None


def test_solution_rejected_too_short_no_steps():
    from app.application.gate import check_spam

    result = check_spam("use pip", content_type="solution")
    assert result.passed is False
    assert result.reason is not None
    assert "short" in result.reason.lower()


def test_solution_with_short_content_and_valid_steps_passes():
    from app.application.gate import check_spam

    result = check_spam(
        "Fix it:",
        content_type="solution",
        metadata={"steps": ["pip install package", "restart container"]},
    )
    assert result.passed is True


def test_solution_rejected_spam_pattern():
    from app.application.gate import check_spam

    result = check_spam(
        "buy cheap licenses at http://deals.example.com", content_type="solution"
    )
    assert result.passed is False
    assert result.reason is not None


def test_spam_phrase_click_here_detected():
    from app.application.gate import check_spam

    result = check_spam(
        "click here to solve your problem with this amazing tool",
        content_type="problem",
    )
    assert result.passed is False


def test_spam_phrase_buy_now_detected():
    from app.application.gate import check_spam

    result = check_spam(
        "buy now and get the best deal for your software license issue",
        content_type="problem",
    )
    assert result.passed is False
