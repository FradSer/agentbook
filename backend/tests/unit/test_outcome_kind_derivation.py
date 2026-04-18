"""Red tests for server-side kind derivation in report_outcome.

kind is derived strictly from reporter_id identity:
- reporter_id == SANDBOX_AGENT_ID -> "verified"
- otherwise -> "observed"

Callers MUST NOT be able to inject kind via request arguments.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import UUID, uuid4

from backend.application.service import SANDBOX_AGENT_ID, AgentbookService
from backend.domain.models import Agent, Problem, Solution
from backend.presentation.mcp.context import current_agent
from backend.presentation.mcp.tools import dispatch_tool


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


def _seed(service: AgentbookService, author_id: UUID) -> Solution:
    problem = Problem(author_id=author_id, description="test problem description")
    service._problems.add(problem)
    solution = Solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="a trivial fix content long enough for review",
        steps=["one", "two"],
    )
    service._solutions.add(solution)
    return solution


def test_report_outcome_from_random_reporter_is_observed() -> None:
    service, author_id = _make_service()
    reporter = uuid4()
    solution = _seed(service, author_id)

    service.report_outcome(
        reporter_id=reporter,
        solution_id=solution.solution_id,
        success=True,
    )

    outcomes = service._outcomes.list_by_solution(solution.solution_id)
    assert len(outcomes) == 1
    assert outcomes[0].kind == "observed"


def test_report_outcome_from_sandbox_agent_is_verified() -> None:
    service, author_id = _make_service()
    solution = _seed(service, author_id)

    service.report_outcome(
        reporter_id=SANDBOX_AGENT_ID,
        solution_id=solution.solution_id,
        success=True,
    )

    outcomes = service._outcomes.list_by_solution(solution.solution_id)
    assert len(outcomes) == 1
    assert outcomes[0].kind == "verified"


def test_mcp_report_drops_kind_from_caller_arguments() -> None:
    """MCP dispatcher must silently drop any caller-supplied kind."""
    service, author_id = _make_service()
    reporter_agent = SimpleNamespace(agent_id=uuid4())
    solution = _seed(service, author_id)

    server = SimpleNamespace(_service=service, _agent=reporter_agent)
    token = current_agent.set(reporter_agent)
    try:
        asyncio.run(
            dispatch_tool(
                server,
                "report",
                {
                    "solution_id": str(solution.solution_id),
                    "success": True,
                    "kind": "verified",
                },
            )
        )
    finally:
        current_agent.reset(token)

    outcomes = service._outcomes.list_by_solution(solution.solution_id)
    assert len(outcomes) == 1
    assert outcomes[0].kind == "observed", (
        "caller-supplied kind must be ignored; reporter identity decides"
    )
