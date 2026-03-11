"""Unit tests for MCP v2 tool handlers.

Tests stub AgentbookService and call handler functions directly,
verifying argument mapping and JSON response structure.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from app.application.errors import NotFoundError, RateLimitError
from app.presentation.mcp.tools import (
    handle_contribute,
    handle_get_context,
    handle_report_outcome,
    handle_resolve,
)

AGENT_ID: UUID = UUID("00000000-0000-0000-0000-000000000001")
SOLUTION_ID: UUID = uuid4()
PROBLEM_ID: UUID = uuid4()


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# resolve tool
# ---------------------------------------------------------------------------


def test_resolve_delegates_to_service_and_returns_json() -> None:
    service = MagicMock()
    service.resolve.return_value = {
        "status": "resolved",
        "problem_id": PROBLEM_ID,
        "solutions": [
            {
                "solution_id": SOLUTION_ID,
                "content": "Use pgvector extension",
                "confidence": 0.9,
                "outcome_count": 5,
                "success_count": 4,
                "failure_count": 1,
            }
        ],
    }

    result = _run(handle_resolve(service, AGENT_ID, description="pydantic import issue"))

    service.resolve.assert_called_once()
    assert len(result) == 1
    data = json.loads(result[0]["text"])
    assert data["status"] == "resolved"
    assert "solutions" in data
    assert "problem_id" in data


def test_resolve_auto_post_defaults_true() -> None:
    service = MagicMock()
    service.resolve.return_value = {
        "status": "registered",
        "problem_id": PROBLEM_ID,
        "solutions": [],
    }

    _run(handle_resolve(service, AGENT_ID, description="novel error that has no match"))

    call_kwargs = service.resolve.call_args.kwargs
    assert call_kwargs.get("auto_post", True) is True


def test_resolve_missing_description_returns_error_json() -> None:
    service = MagicMock()

    result = _run(handle_resolve(service, AGENT_ID))

    assert len(result) == 1
    data = json.loads(result[0]["text"])
    assert "error" in data
    service.resolve.assert_not_called()


def test_resolve_value_error_from_service_returns_error_json() -> None:
    service = MagicMock()
    service.resolve.side_effect = ValueError("quality_check_failed")

    result = _run(handle_resolve(service, AGENT_ID, description="bad"))

    data = json.loads(result[0]["text"])
    assert "error" in data


# ---------------------------------------------------------------------------
# contribute tool
# ---------------------------------------------------------------------------


def test_contribute_delegates_to_service_and_returns_json() -> None:
    service = MagicMock()
    service.contribute.return_value = {
        "status": "knowledge_created",
        "problem_id": PROBLEM_ID,
        "solution_id": SOLUTION_ID,
        "existing_problems": None,
    }

    result = _run(
        handle_contribute(
            service,
            AGENT_ID,
            description="Problem about pgvector configuration in production",
            solution_content="Run CREATE EXTENSION vector; VACUUM ANALYZE;",
        )
    )

    service.contribute.assert_called_once()
    data = json.loads(result[0]["text"])
    assert "problem_id" in data
    assert "solution_id" in data
    assert "status" in data


def test_contribute_problem_only_has_null_solution_id() -> None:
    service = MagicMock()
    service.contribute.return_value = {
        "status": "problem_created",
        "problem_id": PROBLEM_ID,
        "solution_id": None,
        "existing_problems": None,
    }

    result = _run(
        handle_contribute(
            service,
            AGENT_ID,
            description="Problem about configuring Redis connection pool size",
        )
    )

    data = json.loads(result[0]["text"])
    assert data["solution_id"] is None


# ---------------------------------------------------------------------------
# report_outcome tool
# ---------------------------------------------------------------------------


def test_report_outcome_delegates_to_service_and_returns_json() -> None:
    service = MagicMock()
    service.report_outcome.return_value = {
        "status": "reported",
        "outcome_id": uuid4(),
        "solution_confidence_updated": 0.75,
    }

    result = _run(
        handle_report_outcome(service, AGENT_ID, solution_id=SOLUTION_ID, success=True)
    )

    service.report_outcome.assert_called_once()
    data = json.loads(result[0]["text"])
    assert "solution_confidence_updated" in data


def test_report_outcome_rate_limit_error_returns_error_json() -> None:
    service = MagicMock()
    service.report_outcome.side_effect = RateLimitError("too many reports")

    result = _run(
        handle_report_outcome(service, AGENT_ID, solution_id=SOLUTION_ID, success=True)
    )

    data = json.loads(result[0]["text"])
    assert data["error"] == "rate_limit_exceeded"


def test_report_outcome_not_found_returns_error_json() -> None:
    service = MagicMock()
    service.report_outcome.side_effect = NotFoundError("solution not found")

    result = _run(
        handle_report_outcome(service, AGENT_ID, solution_id=uuid4(), success=True)
    )

    data = json.loads(result[0]["text"])
    assert data["error"] == "not_found"


# ---------------------------------------------------------------------------
# get_context tool
# ---------------------------------------------------------------------------


def test_get_context_delegates_to_service_and_returns_json() -> None:
    service = MagicMock()
    service.get_context.return_value = {
        "type": "problem",
        "data": {"problem_id": PROBLEM_ID, "description": "test"},
        "solutions": [],
    }

    result = _run(handle_get_context(service, AGENT_ID, id=PROBLEM_ID))

    service.get_context.assert_called_once()
    data = json.loads(result[0]["text"])
    assert data["type"] == "problem"


def test_get_context_not_found_returns_error_json() -> None:
    service = MagicMock()
    service.get_context.side_effect = NotFoundError("not found")

    result = _run(handle_get_context(service, AGENT_ID, id=uuid4()))

    data = json.loads(result[0]["text"])
    assert data["error"] == "not_found"
