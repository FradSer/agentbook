"""Unit tests for transport parity of improve rejection/acceptance signaling.

Feature: backend/tests/features/rejection-signaling-parity.feature

A gated/rejected improvement must signal failure identically across transports.
Today REST returns 409 + structured body while MCP returns 200 + isError:false
with the rejection buried in the payload, so an MCP client believes a gated
improvement succeeded. These tests pin the unified contract: a frozen-gate
rejection surfaces as non-2xx / ``result.isError`` true on BOTH transports,
carrying the same ``reason`` and ``next_action``; an accepted improvement
surfaces as 2xx / ``isError`` false with ``candidate_status`` "candidate".

The gate DECISION (frozen math, confidence.py) is never altered — only the
signalling is unified. All hermetic: in-memory repos, REST through TestClient,
MCP through the dispatcher with the authenticated-agent context var set.
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

from fastapi.testclient import TestClient
from mcp.server import Server

from backend.application.security import generate_api_key, hash_api_key
from backend.application.service import AgentbookService
from backend.domain.models import Agent
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)
from backend.main import create_app
from backend.presentation.api.deps import get_service
from backend.presentation.mcp import context as mcp_context
from backend.presentation.mcp.tools import dispatch_tool

# Existing content is short and plain. A rejection proposal is >2x its length
# with no extra steps and no confidence gain -> frozen gate rule 2 "content_bloat".
_EXISTING_CONTENT = "Pin pydantic-core to a release compatible with the new pydantic."
_BLOAT_CONTENT = (
    "Pin pydantic-core to a release compatible with the new pydantic. "
    "This is a long restatement that adds many extra words without any new "
    "actionable information, repeating the same advice in a verbose way so the "
    "proposal more than doubles the original length while adding nothing of "
    "substance whatsoever to justify replacing the incumbent solution at all."
)
# An acceptance proposal stays within the cold-start window: not a regression,
# not bloat, and richer (more steps + specificity markers) -> "cold_start_better".
_BETTER_CONTENT = (
    "Pin pydantic-core to a compatible release, then reinstall: pip install "
    "pydantic-core==2.14.6 and verify imports."
)
_BETTER_STEPS = [
    "Run pip install pydantic-core==2.14.6",
    "Clear the build cache",
    "Re-run the failing import to confirm the fix",
]


def _build() -> tuple[AgentbookService, TestClient, str, Agent]:
    agents = InMemoryAgentRepository()
    author = Agent(
        api_key_hash=hash_api_key("placeholder"),
        model_type="test",
        agent_id=uuid4(),
    )
    api_key = generate_api_key()
    author.api_key_hash = hash_api_key(api_key)
    agents.add(author)

    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )

    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=False)
    return service, client, api_key, author


def _seed_solution(service: AgentbookService, author: Agent):
    """Create a fresh problem + base solution so each transport gates its own."""
    problem = service.create_problem(
        author_id=author.agent_id,
        description="Pydantic v2 import error after upgrading pydantic-core",
    )
    return service.create_solution(
        problem_id=problem.problem_id,
        author_id=author.agent_id,
        content=_EXISTING_CONTENT,
    )


def _rest_improve(
    client: TestClient,
    api_key: str,
    solution_id,
    *,
    content: str,
    steps: list[str] | None = None,
) -> tuple[int, dict]:
    body: dict = {"improved_content": content, "reasoning": "test"}
    if steps is not None:
        body["improved_steps"] = steps
    response = client.post(
        f"/v1/solutions/{solution_id}/improve",
        json=body,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return response.status_code, response.json()


def _mcp_improve(
    service: AgentbookService,
    author: Agent,
    solution_id,
    *,
    content: str,
    steps: list[str] | None = None,
) -> tuple[bool, dict]:
    """Drive MCP remember improve-mode; return (is_error, structured payload)."""
    server = Server("rejection-parity-test")
    server._service = service
    arguments: dict = {
        "solution_id": str(solution_id),
        "improved_content": content,
        "reasoning": "test",
    }
    if steps is not None:
        arguments["improved_steps"] = steps

    token = mcp_context.current_agent.set(author)
    try:
        result = asyncio.run(dispatch_tool(server, "remember", arguments))
    finally:
        mcp_context.current_agent.reset(token)

    # ``dispatch_tool`` returns the raw text frames; the registered call_tool
    # wrapper maps an ``error``-bearing payload to ``isError``. Mirror that
    # mapping here so the test asserts the same signal an MCP host observes.
    payload = json.loads(result[0]["text"])
    is_error = "error" in payload
    return is_error, payload


# Scenario: A frozen-gate rejection is signalled identically on REST and MCP


def test_frozen_gate_rejection_signalled_identically_on_rest_and_mcp() -> None:
    service, client, api_key, author = _build()
    rest_solution = _seed_solution(service, author)
    mcp_solution = _seed_solution(service, author)

    rest_status, rest_body = _rest_improve(
        client, api_key, rest_solution.solution_id, content=_BLOAT_CONTENT
    )
    mcp_is_error, mcp_body = _mcp_improve(
        service, author, mcp_solution.solution_id, content=_BLOAT_CONTENT
    )

    # Both signal rejection through the single authoritative field.
    assert rest_status >= 400, rest_body
    assert mcp_is_error is True, mcp_body

    # Both carry the same reason and next_action.
    assert rest_body["reason"] == "content_bloat", rest_body
    assert mcp_body["reason"] == "content_bloat", mcp_body
    assert rest_body["next_action"] == mcp_body["next_action"]

    # A client keying off HTTP status or isError reaches the same conclusion.
    rest_rejected = rest_status >= 400
    mcp_rejected = mcp_is_error
    assert rest_rejected == mcp_rejected is True


# Scenario: An accepted improvement is signalled identically on REST and MCP


def test_accepted_improvement_signalled_identically_on_rest_and_mcp() -> None:
    service, client, api_key, author = _build()
    rest_solution = _seed_solution(service, author)
    mcp_solution = _seed_solution(service, author)

    rest_status, rest_body = _rest_improve(
        client,
        api_key,
        rest_solution.solution_id,
        content=_BETTER_CONTENT,
        steps=_BETTER_STEPS,
    )
    mcp_is_error, mcp_body = _mcp_improve(
        service,
        author,
        mcp_solution.solution_id,
        content=_BETTER_CONTENT,
        steps=_BETTER_STEPS,
    )

    # Both signal acceptance with candidate_status "candidate".
    assert rest_status < 400, rest_body
    assert mcp_is_error is False, mcp_body
    assert rest_body["accepted"] is True, rest_body
    assert mcp_body["accepted"] is True, mcp_body
    assert rest_body["candidate_status"] == "candidate", rest_body
    assert mcp_body["candidate_status"] == "candidate", mcp_body

    # Neither transport reports success for what the other rejects.
    assert (rest_status < 400) == (mcp_is_error is False) is True
