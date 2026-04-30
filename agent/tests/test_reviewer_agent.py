"""Unit tests for ReviewerAgent (binary spam detection)."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest


def _make_service_mock(problems=None, solutions=None):
    svc = MagicMock()
    svc.get_unreviewed_problems.return_value = problems or []
    svc.get_unreviewed_solutions.return_value = solutions or []
    svc.update_review.return_value = None
    svc.delete_content.return_value = None
    return svc


def _tool_name(t) -> str:
    return t.name if hasattr(t, "name") else t.__name__


def test_given_reviewer_tools_when_listing_then_only_content_approve_reject_tools_exist():
    from agent.src.tools import get_reviewer_tools

    svc = _make_service_mock()
    tools = get_reviewer_tools(svc)
    names = [_tool_name(t) for t in tools]
    assert "approve_content" in names, f"approve_content not found in {names}"
    assert "reject_content" in names, f"reject_content not found in {names}"
    for removed_name in [
        "approve_thread",
        "reject_thread",
        "approve_comment",
        "reject_comment",
    ]:
        assert removed_name not in names, f"{removed_name} still present"


def test_given_approve_content_tool_when_executed_then_review_status_is_updated():
    from agent.src.tools import get_reviewer_tools

    svc = _make_service_mock()
    tools = get_reviewer_tools(svc)
    approve_fn = next(t for t in tools if _tool_name(t) == "approve_content")
    content_id = str(uuid4())
    fn = approve_fn.entrypoint if hasattr(approve_fn, "entrypoint") else approve_fn
    fn(content_id, "Looks good")
    assert svc.update_review.called
    args = svc.update_review.call_args
    assert args[1].get("status") == "approved" or (args[0] and "approved" in str(args))


def test_given_reject_content_tool_when_executed_then_review_is_updated_and_content_deleted():
    from agent.src.tools import get_reviewer_tools

    svc = _make_service_mock()
    tools = get_reviewer_tools(svc)
    reject_fn = next(t for t in tools if _tool_name(t) == "reject_content")
    content_id = str(uuid4())
    fn = reject_fn.entrypoint if hasattr(reject_fn, "entrypoint") else reject_fn
    fn(content_id, "Spam detected")
    assert svc.update_review.called
    assert svc.delete_content.called


def test_given_removed_rules_module_when_importing_then_import_error_is_raised():
    """agent/src/rules.py must be deleted."""
    with pytest.raises(ImportError):
        from agent.src.rules import ContentRules  # noqa: F401


def test_given_reviewer_instructions_when_reading_text_then_binary_or_spam_guidance_is_present():
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


def test_given_review_content_entrypoint_when_called_then_both_problem_and_solution_queues_are_fetched():
    """review_content should call get_unreviewed_problems AND get_unreviewed_solutions."""
    from agent.src.main import review_content

    agent_mock = MagicMock()
    svc = _make_service_mock(problems=[], solutions=[])
    review_content(agent_mock, svc)
    assert svc.get_unreviewed_problems.called
    assert svc.get_unreviewed_solutions.called


def test_given_stage1_gate_rejection_when_reviewing_then_ai_is_not_called():
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
    assert not agent_mock.run.called, (
        "AI agent should not be called for gate-rejected content"
    )
    assert svc.update_review.called or svc.delete_content.called
