"""MCP verify tool contract.

Authenticated callers run a synchronous sandbox-backed verification of a
solution and receive the pass/fail verdict (the confidence-independent trust
signal). A solution with no runnable Python is reported not_verifiable.
Anonymous callers receive the standard auth error; no sandbox run is triggered.
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
        content=(
            "Guard the lookup with a default.\n\n"
            "```python\nd = {}\nprint(d.get('x', 'fallback'))\n```\n"
        ),
        steps=["use dict.get with a default"],
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


def test_verify_authenticated_returns_pass_fail_verdict() -> None:
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
    # The agent gets the actual sandbox verdict, not an opaque 'queued'.
    assert body.get("status") == "verified"
    assert body.get("passed") is True
    assert body.get("exit_code") == 0
    assert "duration_seconds" in body


def test_verify_prose_solution_is_not_verifiable() -> None:
    service, author_id = _build_service(with_sandbox=_FakeSandbox())
    problem = Problem(
        author_id=author_id, description="x", error_signature="KeyError: 'x'"
    )
    service._problems.add(problem)
    solution = Solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Just handle the key error carefully in your code path.",
        steps=["check the key first"],
    )
    service._solutions.add(solution)
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
    assert body.get("status") == "not_verifiable"
    assert "Python" in body.get("reason", "")
