"""Unit tests for unified ReviewerAgent (binary spam detection, V3)."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch
from uuid import uuid4

import pytest


def _make_service_mock(problems=None, solutions=None):
    svc = MagicMock()
    svc.get_unreviewed_problems.return_value = problems or []
    svc.get_unreviewed_solutions.return_value = solutions or []
    svc.update_review.return_value = None
    svc.delete_content.return_value = None
    return svc


def test_get_reviewer_tools_returns_two_tools():
    from agent.src.tools import get_reviewer_tools

    svc = _make_service_mock()
    tools = get_reviewer_tools(svc)
    names = [t.name if hasattr(t, "name") else t.__name__ for t in tools]
    # Must have approve_content and reject_content
    assert "approve_content" in names, f"approve_content not found in {names}"
    assert "reject_content" in names, f"reject_content not found in {names}"
    # Must NOT have old V1 tools
    assert "approve_thread" not in names, "V1 approve_thread still present"
    assert "reject_thread" not in names, "V1 reject_thread still present"
    assert "approve_comment" not in names, "V1 approve_comment still present"
    assert "reject_comment" not in names, "V1 reject_comment still present"


def test_approve_content_calls_update_review():
    from agent.src.tools import get_reviewer_tools

    svc = _make_service_mock()
    tools = get_reviewer_tools(svc)
    approve_fn = next(
        t for t in tools
        if (t.name if hasattr(t, "name") else t.__name__) == "approve_content"
    )
    content_id = str(uuid4())
    # Call the tool's underlying function
    fn = approve_fn.entrypoint if hasattr(approve_fn, "entrypoint") else approve_fn
    result = fn(content_id, "Looks good")
    assert svc.update_review.called
    args = svc.update_review.call_args
    assert args[1].get("status") == "approved" or (args[0] and "approved" in str(args))


def test_reject_content_calls_update_review_and_delete():
    from agent.src.tools import get_reviewer_tools

    svc = _make_service_mock()
    tools = get_reviewer_tools(svc)
    reject_fn = next(
        t for t in tools
        if (t.name if hasattr(t, "name") else t.__name__) == "reject_content"
    )
    content_id = str(uuid4())
    fn = reject_fn.entrypoint if hasattr(reject_fn, "entrypoint") else reject_fn
    result = fn(content_id, "Spam detected")
    assert svc.update_review.called
    assert svc.delete_content.called


def test_rules_module_no_longer_importable():
    """agent/src/rules.py must be deleted."""
    with pytest.raises(ImportError):
        from agent.src.rules import ContentRules  # noqa: F401


def test_reviewer_agent_instructions_mention_binary_detection():
    from agent.src import reviewer_agent

    instructions = (
        reviewer_agent.REVIEWER_INSTRUCTIONS
        if hasattr(reviewer_agent, "REVIEWER_INSTRUCTIONS")
        else ""
    )
    lower = instructions.lower()
    assert "spam" in lower or "binary" in lower or "approve" in lower, (
        "REVIEWER_INSTRUCTIONS should mention spam detection or binary approve/reject"
    )


def test_review_content_fetches_both_problems_and_solutions():
    """review_content should call get_unreviewed_problems AND get_unreviewed_solutions."""
    from agent.src.main import review_content

    agent_mock = MagicMock()
    svc = _make_service_mock(problems=[], solutions=[])
    review_content(agent_mock, svc)
    assert svc.get_unreviewed_problems.called
    assert svc.get_unreviewed_solutions.called


def test_stage1_gate_rejection_bypasses_ai():
    """A problem that fails Stage 1 gate is auto-rejected without calling AI."""
    from agent.src.main import review_content
    from backend.domain.models import Problem

    short_problem = Problem(
        author_id=uuid4(),
        description="help",  # too short — fails gate
    )
    agent_mock = MagicMock()
    svc = _make_service_mock(problems=[short_problem], solutions=[])
    review_content(agent_mock, svc)
    # AI agent should NOT have been called (no run/prompt calls)
    assert not agent_mock.run.called, "AI agent should not be called for gate-rejected content"
    # But update_review or delete_content should be called
    assert svc.update_review.called or svc.delete_content.called
