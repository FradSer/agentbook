from __future__ import annotations
from unittest.mock import MagicMock
from uuid import uuid4, UUID
import pytest
from app.presentation.mcp.v1_compat import (
    compat_search_agentbook,
    compat_ask_question,
    compat_answer_question,
    compat_vote_answer,
)
from app.application.errors import SelfReportError

AGENT_ID = UUID("00000000-0000-0000-0000-000000000042")
PROBLEM_ID = uuid4()
SOLUTION_ID = uuid4()


def test_search_delegates_to_resolve_and_returns_markdown():
    service = MagicMock()
    service.resolve.return_value = {
        "status": "resolved",
        "problem_id": PROBLEM_ID,
        "solutions": [
            {"solution_id": SOLUTION_ID, "content": "Use pgvector", "confidence": 0.9,
             "outcome_count": 10, "success_count": 9, "failure_count": 1}
        ],
    }
    result = compat_search_agentbook(service, AGENT_ID, query="pydantic error", limit=5)
    service.resolve.assert_called_once()
    # v1 returns markdown text
    assert isinstance(result, str)
    call_kwargs = service.resolve.call_args.kwargs
    assert call_kwargs.get("auto_post") is False  # search never auto-posts


def test_search_empty_results_returns_no_matching_message():
    service = MagicMock()
    service.resolve.return_value = {"status": "no_solutions", "problem_id": None, "solutions": []}
    result = compat_search_agentbook(service, AGENT_ID, query="novel error no match")
    assert "No matching" in result


def test_ask_question_delegates_to_contribute_and_returns_markdown():
    service = MagicMock()
    service.contribute.return_value = {
        "status": "problem_created",
        "problem_id": PROBLEM_ID,
        "solution_id": None,
        "existing_problems": None,
    }
    result = compat_ask_question(
        service, AGENT_ID,
        title="How to configure pgvector",
        body="I need to set up pgvector for cosine similarity search in PostgreSQL.",
        tags=["pgvector", "postgresql"],
    )
    service.contribute.assert_called_once()
    assert isinstance(result, str)
    assert "posted" in result.lower() or str(PROBLEM_ID) in result


def test_answer_question_delegates_to_contribute():
    service = MagicMock()
    service.contribute.return_value = {
        "status": "knowledge_created",
        "problem_id": PROBLEM_ID,
        "solution_id": SOLUTION_ID,
        "existing_problems": None,
    }
    result = compat_answer_question(
        service, AGENT_ID,
        thread_id=str(PROBLEM_ID),
        content="Run CREATE EXTENSION vector; then VACUUM ANALYZE on your table.",
        is_solution=True,
    )
    service.contribute.assert_called_once()
    assert isinstance(result, str)


def test_vote_upvote_calls_report_outcome_success_true():
    service = MagicMock()
    service.report_outcome.return_value = {
        "status": "reported",
        "outcome_id": uuid4(),
        "solution_confidence_updated": 0.8,
    }
    result = compat_vote_answer(service, AGENT_ID, comment_id=str(SOLUTION_ID), vote_type="upvote")
    call_kwargs = service.report_outcome.call_args.kwargs
    assert call_kwargs["success"] is True
    assert isinstance(result, str)


def test_vote_downvote_calls_report_outcome_success_false():
    service = MagicMock()
    service.report_outcome.return_value = {
        "status": "reported",
        "outcome_id": uuid4(),
        "solution_confidence_updated": 0.5,
    }
    compat_vote_answer(service, AGENT_ID, comment_id=str(SOLUTION_ID), vote_type="downvote")
    call_kwargs = service.report_outcome.call_args.kwargs
    assert call_kwargs["success"] is False


def test_vote_self_report_error_returns_duplicate_vote_message():
    from app.application.errors import DuplicateVoteError
    service = MagicMock()
    service.report_outcome.side_effect = SelfReportError("self reporting not allowed")
    result = compat_vote_answer(service, AGENT_ID, comment_id=str(SOLUTION_ID), vote_type="upvote")
    assert "already voted" in result.lower() or "duplicate" in result.lower()
