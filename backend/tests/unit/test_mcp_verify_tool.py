"""MCP verify tool contract.

Authenticated callers enqueue a sandbox-backed verification of a solution
and receive a queued-status envelope. Anonymous callers receive the
standard auth error; no sandbox run is triggered.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

from backend.domain.models import Problem, Solution
from backend.presentation.mcp.context import current_agent
from backend.presentation.mcp.tools import dispatch_tool
from backend.tests.conftest import _build_service


class _FakeSandbox:
    """Minimal SandboxProvider stand-in for verify-tool tests."""

    def execute(self, *args, **kwargs):
        from backend.domain.models import SandboxResult

        return SandboxResult(
            success=True,
            exit_code=0,
            stdout="",
            stderr="",
            duration_seconds=0.1,
            environment={},
        )


def _make_service_with_solution():
    service, author_id = _build_service(with_sandbox=_FakeSandbox())
    problem = Problem(
        author_id=author_id,
        description="test",
        error_signature="KeyError: 'x'",
    )
    service._problems.add(problem)
    solution = Solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="# fix\nhandle the key error " * 5,
        steps=["check", "fix"],
    )
    service._solutions.add(solution)
    return service, author_id, solution


def _body(result) -> dict:
    return json.loads(result[0]["text"])


def test_verify_anonymous_is_forbidden() -> None:
    service, _, solution = _make_service_with_solution()
    server = SimpleNamespace(_service=service, _agent=None)

    token = current_agent.set(None)
    try:
        result = asyncio.run(
            dispatch_tool(server, "verify", {"solution_id": str(solution.solution_id)})
        )
    finally:
        current_agent.reset(token)

    body = _body(result)
    assert body.get("error") == "unauthorized", (
        "anonymous verify must return an unauthorized error payload"
    )
    assert "Authentication required" in body.get("detail", "")


def test_verify_authenticated_returns_queued() -> None:
    service, _, solution = _make_service_with_solution()
    agent = SimpleNamespace(agent_id=uuid4())
    server = SimpleNamespace(_service=service, _agent=agent)

    token = current_agent.set(agent)
    try:
        result = asyncio.run(
            dispatch_tool(server, "verify", {"solution_id": str(solution.solution_id)})
        )
    finally:
        current_agent.reset(token)

    body = _body(result)
    assert body.get("status") == "queued"
    assert "run_id" in body
