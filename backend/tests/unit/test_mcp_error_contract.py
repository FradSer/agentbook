"""Unit tests for the MCP error contract.

Feature: backend/tests/features/mcp-error-contract.feature

Distinguishes protocol-layer JSON-RPC errors (-32601 unknown method, -32700
parse error) from tool-layer ``isError`` envelopes, the ``problem_id`` alias on
``trace``, an unrecognized-argument message that does not lie ("id is
required"), and the three differentiated auth-failure details. All hermetic:
in-memory repos, ``/mcp`` driven through a context-managed ``TestClient`` (which
runs the lifespan that boots the session manager) and the dispatcher driven
directly for tool-layer assertions.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from mcp.server import Server

from backend.domain.models import Agent
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)
from backend.main import create_app
from backend.presentation.mcp import auth as mcp_auth
from backend.presentation.mcp import context as mcp_context
from backend.presentation.mcp.tools import dispatch_tool

_MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def _service_with_problem() -> tuple[object, str, str]:
    """Build a service with one problem; return (service, agent_id, problem_id)."""
    agents = InMemoryAgentRepository()
    author = Agent(api_key_hash="h", model_type="test", agent_id=uuid4())
    agents.add(author)
    from backend.application.service import AgentbookService

    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    result = service.contribute(
        author_id=author.agent_id,
        description="Pydantic v2 import error after upgrade",
        solution_content="Pin pydantic-core to a compatible release.",
    )
    return service, str(author.agent_id), result["problem_id"]


def _server_for(service) -> Server:
    server = Server("mcp-error-contract-test")
    server._service = service
    return server


def _dispatch(server: Server, name: str, arguments: dict) -> dict:
    result = asyncio.run(dispatch_tool(server, name, arguments))
    return json.loads(result[0]["text"])


# Scenario: Tool-layer error returns the documented isError envelope


def test_anonymous_report_returns_iserror_envelope() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            headers=_MCP_HEADERS,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "report",
                    "arguments": {"solution_id": str(uuid4()), "success": True},
                },
            },
        )
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["isError"] is True
    assert result["structuredContent"]["error"] == "unauthorized"
    text = result["content"][0]["text"]
    assert json.loads(text)["error"] == "unauthorized"


# Scenario: Unknown method returns -32601, not -32602


def test_unknown_method_returns_minus_32601_not_32602() -> None:
    app = create_app()
    with TestClient(app) as client:
        unknown = client.post(
            "/mcp",
            headers=_MCP_HEADERS,
            json={"jsonrpc": "2.0", "id": 2, "method": "foo/bar", "params": {}},
        )
        bad_params = client.post(
            "/mcp",
            headers=_MCP_HEADERS,
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {}},
        )
    unknown_body = unknown.json()
    assert "result" not in unknown_body
    assert unknown_body["error"]["code"] == -32601
    assert "method not found" in unknown_body["error"]["message"].lower()
    # A known method with bad params stays -32602, so the two are distinguishable.
    assert bad_params.json()["error"]["code"] == -32602


# Scenario: Parse and missing-name errors are protocol-layer, and documented


def test_malformed_json_returns_minus_32700_no_result() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post("/mcp", headers=_MCP_HEADERS, content=b"{not valid json")
    body = response.json()
    assert "result" not in body
    assert body["error"]["code"] == -32700


def test_docs_document_protocol_layer_envelope() -> None:
    doc = Path(__file__).resolve().parents[3] / "docs" / "mcp-setup.md"
    text = doc.read_text(encoding="utf-8")
    assert "-32601" in text, "docs must document the unknown-method protocol error"
    assert "-32700" in text, "docs must document the parse-error protocol error"


# Scenario: MCP trace accepts the canonical problem_id alias (transport parity)


def test_trace_accepts_problem_id_alias() -> None:
    service, _, problem_id = _service_with_problem()
    server = _server_for(service)

    by_id = _dispatch(server, "trace", {"id": problem_id})
    by_problem_id = _dispatch(server, "trace", {"problem_id": problem_id})

    assert "error" not in by_id, by_id
    assert "error" not in by_problem_id, by_problem_id
    assert by_id["data"]["problem_id"] == by_problem_id["data"]["problem_id"]
    assert by_id == by_problem_id


# Scenario: Unknown tool argument is reported as unexpected, not "X is required"


def test_unknown_trace_argument_is_named_unrecognized() -> None:
    service, _, problem_id = _service_with_problem()
    server = _server_for(service)

    response = _dispatch(server, "trace", {"resourceId": problem_id})

    detail = response.get("detail", "")
    assert response["error"] == "invalid_input"
    assert "resourceId" in detail, detail
    assert "is required" not in detail.lower(), (
        f"must not misreport a supplied-but-misnamed arg as missing: {detail!r}"
    )


# Scenario Outline: Auth failures distinguish no-key from bad-key


@pytest.fixture()
def _reset_mcp_context():
    agent_token = mcp_context.current_agent.set(None)
    err_token = mcp_auth.current_auth_error.set(None)
    try:
        yield
    finally:
        mcp_context.current_agent.reset(agent_token)
        mcp_auth.current_auth_error.reset(err_token)


def test_auth_detail_no_credentials(_reset_mcp_context) -> None:
    service, _, _ = _service_with_problem()
    server = _server_for(service)
    mcp_auth.current_auth_error.set(None)
    response = _dispatch(
        server, "report", {"solution_id": str(uuid4()), "success": True}
    )
    assert response["error"] == "unauthorized"
    assert response["detail"] == "Authentication required: no credentials provided"


def test_auth_detail_invalid_or_revoked_key(_reset_mcp_context) -> None:
    service, _, _ = _service_with_problem()
    server = _server_for(service)
    mcp_auth.current_auth_error.set(mcp_auth.AuthFailure.INVALID_KEY)
    response = _dispatch(
        server, "report", {"solution_id": str(uuid4()), "success": True}
    )
    assert response["error"] == "unauthorized"
    assert response["detail"] == "Invalid or revoked API key"


def test_auth_detail_malformed_bearer(_reset_mcp_context) -> None:
    service, _, _ = _service_with_problem()
    server = _server_for(service)
    mcp_auth.current_auth_error.set(mcp_auth.AuthFailure.MALFORMED_BEARER)
    response = _dispatch(
        server, "report", {"solution_id": str(uuid4()), "success": True}
    )
    assert response["error"] == "unauthorized"
    assert response["detail"] == "Malformed Authorization header: expected Bearer"


# Scenario: not_found carries a detail naming the missing id


def test_not_found_detail_names_missing_id() -> None:
    service, _, _ = _service_with_problem()
    server = _server_for(service)
    missing = str(uuid4())

    response = _dispatch(server, "trace", {"id": missing})

    assert response["error"] == "not_found"
    assert missing in response.get("detail", ""), response
