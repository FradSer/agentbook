"""Red tests for MCP tool aliasing with 6-month deprecation.

Legacy names (search, contribute, report, inspect) continue to work and
carry deprecation metadata. New memory-shaped names (recall, remember,
trace) are served as first-class tools with inputSchema parity.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

from backend.application.service import AgentbookService
from backend.domain.models import Agent, Problem
from backend.presentation.mcp.context import current_agent
from backend.presentation.mcp.tools import TOOL_DEFINITIONS, dispatch_tool


def _make_service() -> tuple[AgentbookService, UUID]:
    from backend.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
    )

    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(Agent(api_key_hash="author-hash", model_type="test", agent_id=author_id))
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, author_id


def _parse_body(result: list[dict]) -> dict:
    return json.loads(result[0]["text"])


def test_recall_served_and_meta_not_deprecated() -> None:
    service, _ = _make_service()
    server = SimpleNamespace(_service=service, _agent=None)

    result = asyncio.run(dispatch_tool(server, "recall", {"query": "pgvector missing"}))
    body = _parse_body(result)

    assert body.get("_meta", {}).get("deprecated") is False
    # Payload shape matches legacy search — it has results (or empty list).
    assert "results" in body


def test_search_legacy_returns_deprecation_meta() -> None:
    service, _ = _make_service()
    server = SimpleNamespace(_service=service, _agent=None)

    result_new = asyncio.run(
        dispatch_tool(server, "recall", {"query": "pgvector missing"})
    )
    result_legacy = asyncio.run(
        dispatch_tool(server, "search", {"query": "pgvector missing"})
    )

    body_new = _parse_body(result_new)
    body_legacy = _parse_body(result_legacy)

    # Bodies equal apart from _meta envelope.
    body_new.pop("_meta", None)
    legacy_meta = body_legacy.pop("_meta", {})
    assert body_new == body_legacy
    assert legacy_meta == {
        "deprecated": True,
        "replacement": "recall",
        "sunset": "2026-10-18",
    }


def test_tools_list_advertises_both_names_with_equal_input_schema() -> None:
    by_name = {t.name: t for t in TOOL_DEFINITIONS}
    assert "recall" in by_name, "new tool recall must be registered"
    assert "search" in by_name, "legacy tool search must remain for compatibility"
    assert by_name["recall"].inputSchema == by_name["search"].inputSchema
    assert by_name["search"].description.startswith("[DEPRECATED - use recall]")


def test_anonymous_remember_is_forbidden() -> None:
    service, _ = _make_service()
    server = SimpleNamespace(_service=service, _agent=None)
    # No authenticated agent in context var.
    token = current_agent.set(None)
    try:
        try:
            asyncio.run(
                dispatch_tool(
                    server,
                    "remember",
                    {"description": "I solved a thing and want to share it"},
                )
            )
            raised_auth_error = False
        except ValueError as exc:
            raised_auth_error = "Authentication required" in str(exc)
    finally:
        current_agent.reset(token)

    assert raised_auth_error, "anonymous remember must raise the auth-required error"
    # Also confirm no problem was persisted as a side effect.
    assert service._problems.list_all() == []


def test_trace_aliased_to_inspect() -> None:
    service, author = _make_service()
    problem = Problem(author_id=author, description="a test problem")
    service._problems.add(problem)
    server = SimpleNamespace(_service=service, _agent=None)

    trace_result = asyncio.run(
        dispatch_tool(server, "trace", {"id": str(problem.problem_id)})
    )
    inspect_result = asyncio.run(
        dispatch_tool(server, "inspect", {"id": str(problem.problem_id)})
    )

    trace_body = _parse_body(trace_result)
    inspect_body = _parse_body(inspect_result)

    trace_meta = trace_body.pop("_meta", None)
    inspect_meta = inspect_body.pop("_meta", None)

    # Same underlying body.
    assert trace_body == inspect_body
    # New name: not deprecated. Legacy name: deprecated.
    assert trace_meta == {"deprecated": False}
    assert inspect_meta == {
        "deprecated": True,
        "replacement": "trace",
        "sunset": "2026-10-18",
    }
