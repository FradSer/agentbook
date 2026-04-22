"""MCP tool aliasing with 6-month deprecation.

Legacy names (search, contribute, report, inspect) continue to work and
carry deprecation metadata. New memory-shaped names (recall, remember,
trace) are served as first-class tools with inputSchema parity.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.domain.models import Problem
from backend.presentation.mcp.context import current_agent
from backend.presentation.mcp.tools import TOOL_DEFINITIONS, dispatch_tool
from backend.tests.conftest import _build_service


def _parse_body(result: list[dict]) -> dict:
    return json.loads(result[0]["text"])


def _dispatch(server: SimpleNamespace, tool: str, arguments: dict) -> dict:
    return _parse_body(asyncio.run(dispatch_tool(server, tool, arguments)))


def test_given_new_tool_recall_when_dispatched_then_meta_marks_not_deprecated() -> None:
    service, _ = _build_service()
    server = SimpleNamespace(_service=service, _agent=None)

    body = _dispatch(server, "recall", {"query": "pgvector missing"})

    assert body.get("_meta", {}).get("deprecated") is False
    assert "results" in body


@pytest.mark.parametrize(
    ("new_name", "legacy_name", "lookup_args"),
    [
        ("recall", "search", {"query": "pgvector missing"}),
        ("trace", "inspect", {"id": "PROBLEM_ID_PLACEHOLDER"}),
    ],
)
def test_given_new_and_legacy_alias_when_dispatched_then_payloads_match_but_legacy_is_deprecated(
    new_name: str, legacy_name: str, lookup_args: dict[str, str]
) -> None:
    service, _ = _build_service()
    if "id" in lookup_args:
        problem = Problem(author_id=uuid4(), description="a test problem")
        service._problems.add(problem)
        lookup_args = {"id": str(problem.problem_id)}

    server = SimpleNamespace(_service=service, _agent=None)

    body_new = _dispatch(server, new_name, lookup_args)
    body_legacy = _dispatch(server, legacy_name, lookup_args)

    body_new.pop("_meta", None)
    legacy_meta = body_legacy.pop("_meta", {})
    assert body_new == body_legacy
    assert legacy_meta == {
        "deprecated": True,
        "replacement": new_name,
        "sunset": "2026-10-18",
    }


def test_tools_list_advertises_both_names_with_equal_input_schema() -> None:
    by_name = {t.name: t for t in TOOL_DEFINITIONS}
    assert "recall" in by_name, "new tool recall must be registered"
    assert "search" in by_name, "legacy tool search must remain for compatibility"
    assert by_name["recall"].inputSchema == by_name["search"].inputSchema
    assert by_name["search"].description.startswith("[DEPRECATED - use recall]")


def test_given_anonymous_agent_when_calling_remember_then_unauthorized_payload_and_no_write_occurs() -> (
    None
):
    service, _ = _build_service()
    server = SimpleNamespace(_service=service, _agent=None)
    token = current_agent.set(None)
    try:
        result = asyncio.run(
            dispatch_tool(
                server,
                "remember",
                {"description": "I solved a thing and want to share it"},
            )
        )
    finally:
        current_agent.reset(token)

    body = _parse_body(result)
    assert body.get("error") == "unauthorized", (
        "anonymous remember must return an unauthorized error payload"
    )
    assert "Authentication required" in body.get("detail", "")
    assert service._problems.list_all() == [], (
        "no write must occur for anonymous callers"
    )
