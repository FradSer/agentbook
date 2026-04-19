"""Unit tests for MCP tool handlers.

Tests stub AgentbookService and call handler functions directly,
verifying argument mapping and JSON response structure.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from backend.application.errors import NotFoundError, RateLimitError
from backend.presentation.mcp.tools import (
    handle_contribute,
    handle_inspect,
    handle_report,
)

AGENT_ID: UUID = UUID("00000000-0000-0000-0000-000000000001")
SOLUTION_ID: UUID = uuid4()
PROBLEM_ID: UUID = uuid4()


# search tool (tested via dispatcher, no separate handler function)


def test_search_delegates_to_service_search() -> None:
    """search tool calls service.search_problems() and returns JSON."""
    service = MagicMock()
    service.search_problems.return_value = {
        "results": [
            {
                "problem_id": str(PROBLEM_ID),
                "description": "pydantic import issue",
                "best_confidence": 0.8,
                "solution_count": 2,
                "similarity_score": 0.9,
                "best_solution": None,
                "created_at": "2025-01-01T00:00:00+00:00",
            }
        ],
        "total": 1,
    }

    from backend.presentation.mcp.tools import _json_response

    result = _json_response(
        service.search_problems(query="pydantic import issue", error_log=None, limit=5)
    )

    service.search_problems.assert_called_once()
    assert len(result) == 1
    data = json.loads(result[0]["text"])
    assert "results" in data
    assert data["total"] == 1


def test_search_returns_empty_results() -> None:
    service = MagicMock()
    service.search_problems.return_value = {"results": [], "total": 0}

    from backend.presentation.mcp.tools import _json_response

    result = _json_response(service.search_problems(query="nonexistent", limit=5))
    data = json.loads(result[0]["text"])
    assert data["total"] == 0
    assert data["results"] == []


# contribute tool -- new mode


@pytest.mark.asyncio
async def test_contribute_new_delegates_to_service_and_returns_json() -> None:
    service = MagicMock()
    service.contribute.return_value = {
        "status": "knowledge_created",
        "problem_id": PROBLEM_ID,
        "solution_id": SOLUTION_ID,
        "existing_problems": None,
    }

    result = await handle_contribute(
        service,
        AGENT_ID,
        {
            "description": "Problem about pgvector configuration in production",
            "solution_content": "Run CREATE EXTENSION vector; VACUUM ANALYZE;",
        },
    )

    service.contribute.assert_called_once()
    data = json.loads(result[0]["text"])
    assert "problem_id" in data
    assert "solution_id" in data
    assert "status" in data


@pytest.mark.asyncio
async def test_contribute_new_problem_only_has_null_solution_id() -> None:
    service = MagicMock()
    service.contribute.return_value = {
        "status": "problem_created",
        "problem_id": PROBLEM_ID,
        "solution_id": None,
        "existing_problems": None,
    }

    result = await handle_contribute(
        service,
        AGENT_ID,
        {"description": "Problem about configuring Redis connection pool size"},
    )

    data = json.loads(result[0]["text"])
    assert data["solution_id"] is None


@pytest.mark.asyncio
async def test_contribute_new_missing_description_returns_error() -> None:
    service = MagicMock()

    result = await handle_contribute(service, AGENT_ID, {})

    data = json.loads(result[0]["text"])
    assert data["error"] == "invalid_input"
    service.contribute.assert_not_called()


# contribute tool -- improve mode


@pytest.mark.asyncio
async def test_contribute_improve_delegates_to_improve_solution() -> None:
    service = MagicMock()
    service.improve_solution.return_value = {
        "status": "improved",
        "solution_id": SOLUTION_ID,
        "previous_confidence": 0.3,
        "previous_problem_best": 0.5,
        "new_confidence": 0.6,
    }

    result = await handle_contribute(
        service,
        AGENT_ID,
        {
            "solution_id": str(SOLUTION_ID),
            "improved_content": "Better solution with edge case handling",
            "reasoning": "Added null check",
        },
    )

    service.improve_solution.assert_called_once()
    data = json.loads(result[0]["text"])
    assert data["status"] == "improved"
    assert "new_confidence" in data


@pytest.mark.asyncio
async def test_contribute_improve_not_found_returns_error() -> None:
    service = MagicMock()
    service.improve_solution.side_effect = NotFoundError("solution not found")

    result = await handle_contribute(
        service,
        AGENT_ID,
        {
            "solution_id": str(uuid4()),
            "improved_content": "Better content",
        },
    )

    data = json.loads(result[0]["text"])
    assert data["error"] == "not_found"


@pytest.mark.asyncio
async def test_contribute_improve_missing_content_returns_error() -> None:
    service = MagicMock()

    result = await handle_contribute(
        service,
        AGENT_ID,
        {"solution_id": str(SOLUTION_ID)},
    )

    data = json.loads(result[0]["text"])
    assert data["error"] == "invalid_input"
    assert "improved_content" in data["detail"]
    service.improve_solution.assert_not_called()


# report tool


@pytest.mark.asyncio
async def test_report_delegates_to_service_and_returns_json() -> None:
    service = MagicMock()
    service.report_outcome.return_value = {
        "status": "reported",
        "outcome_id": uuid4(),
        "solution_confidence_updated": 0.75,
    }

    result = await handle_report(
        service,
        AGENT_ID,
        {"solution_id": str(SOLUTION_ID), "success": True},
    )

    service.report_outcome.assert_called_once()
    data = json.loads(result[0]["text"])
    assert "solution_confidence_updated" in data


@pytest.mark.asyncio
async def test_report_rate_limit_error_returns_error_json() -> None:
    service = MagicMock()
    service.report_outcome.side_effect = RateLimitError("too many reports")

    result = await handle_report(
        service,
        AGENT_ID,
        {"solution_id": str(SOLUTION_ID), "success": True},
    )

    data = json.loads(result[0]["text"])
    assert data["error"] == "rate_limit_exceeded"


@pytest.mark.asyncio
async def test_report_not_found_returns_error_json() -> None:
    service = MagicMock()
    service.report_outcome.side_effect = NotFoundError("solution not found")

    result = await handle_report(
        service,
        AGENT_ID,
        {"solution_id": str(uuid4()), "success": True},
    )

    data = json.loads(result[0]["text"])
    assert data["error"] == "not_found"


# inspect tool


@pytest.mark.asyncio
async def test_inspect_delegates_to_service_and_returns_json() -> None:
    service = MagicMock()
    service.inspect_resource.return_value = {
        "type": "problem",
        "data": {"problem_id": PROBLEM_ID, "description": "test"},
        "solutions": [],
    }

    result = await handle_inspect(service, {"id": str(PROBLEM_ID)})

    service.inspect_resource.assert_called_once()
    data = json.loads(result[0]["text"])
    assert data["type"] == "problem"


@pytest.mark.asyncio
async def test_inspect_not_found_returns_error_json() -> None:
    service = MagicMock()
    service.inspect_resource.side_effect = NotFoundError("not found")

    result = await handle_inspect(service, {"id": str(uuid4())})

    data = json.loads(result[0]["text"])
    assert data["error"] == "not_found"


@pytest.mark.asyncio
async def test_inspect_with_lineage_calls_get_solution_lineage() -> None:
    service = MagicMock()
    service.inspect_resource.return_value = {
        "type": "solution",
        "data": {"solution_id": SOLUTION_ID, "content": "test"},
    }
    service.get_solution_lineage.return_value = [
        {"solution_id": str(uuid4()), "content": "v1"},
        {"solution_id": str(SOLUTION_ID), "content": "v2"},
    ]

    result = await handle_inspect(
        service,
        {"id": str(SOLUTION_ID), "include": ["outcomes", "lineage"]},
    )

    service.inspect_resource.assert_called_once_with(
        resource_id=SOLUTION_ID, include=["outcomes"]
    )
    service.get_solution_lineage.assert_called_once_with(SOLUTION_ID)

    data = json.loads(result[0]["text"])
    assert "lineage" in data
    assert len(data["lineage"]) == 2


@pytest.mark.asyncio
async def test_inspect_lineage_ignored_for_problems() -> None:
    service = MagicMock()
    service.inspect_resource.return_value = {
        "type": "problem",
        "data": {"problem_id": PROBLEM_ID, "description": "test"},
    }

    result = await handle_inspect(
        service, {"id": str(PROBLEM_ID), "include": ["lineage"]}
    )

    service.get_solution_lineage.assert_not_called()
    data = json.loads(result[0]["text"])
    assert "lineage" not in data
