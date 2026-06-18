"""Verifies features/improve-structured-knowledge-parity.feature.

The service's improve_solution already accepts root_cause_pattern /
localization_cues / verification; these tests pin that BOTH write transports
forward them on the improve verb (REST used to 422-reject, MCP used to silently
drop), and that omitting them still inherits the parent's values.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import Response

from backend.application.service import AgentbookService
from backend.domain.models import Agent
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)
from backend.presentation.api.routes.problems import improve_solution as rest_improve
from backend.presentation.api.schemas import SolutionImproveRequest
from backend.presentation.mcp.tools import handle_contribute

RC = "the pool outlived the event loop it was bound to"
CUES = ["asyncpg/pool.py:close", "grep: 'Event loop is closed'"]
VERI = [{"command": "pytest -k pool", "expected": "pass", "buggy": "RuntimeError"}]


def _service_with_base():
    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(Agent(api_key_hash="h", model_type="test", agent_id=author_id))
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    problem = service.create_problem(
        author_id=author_id,
        description="Async pool raises 'Event loop is closed' on shutdown teardown",
    )
    base = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Bind the pool to the running loop and close it before the loop ends",
        root_cause_pattern="old pattern",
        localization_cues=["old cue"],
        verification=[{"command": "old", "expected": "old"}],
    )
    return service, author_id, base


# Schema: the REST improve model accepts the structured-knowledge fields


def test_improve_request_schema_accepts_structured_knowledge() -> None:
    body = SolutionImproveRequest(
        improved_content="Bind the pool inside the same loop and await close() first",
        root_cause_pattern=RC,
        localization_cues=CUES,
        verification=VERI,
    )
    assert body.root_cause_pattern == RC
    assert body.localization_cues == CUES
    assert body.verification == VERI


# REST improve forwards refined structured knowledge onto the new solution


def test_rest_improve_persists_refined_structured_knowledge() -> None:
    service, author_id, base = _service_with_base()
    body = SolutionImproveRequest(
        improved_content=(
            "Create the pool inside the running loop, await pool.close() before the "
            "loop stops, and never share a pool across loops — full teardown fix"
        ),
        improved_steps=["await pool.close()", "create pool inside the loop"],
        root_cause_pattern=RC,
        localization_cues=CUES,
        verification=VERI,
        reasoning="adds the transferable root cause and repro",
    )
    agent = Agent(api_key_hash="h2", model_type="test", agent_id=author_id)
    result = rest_improve(base.solution_id, body, Response(), service, agent)

    improved = service._solutions.get(UUID(result.solution_id))
    assert improved is not None
    assert improved.root_cause_pattern == RC
    assert improved.localization_cues == CUES
    assert improved.verification == VERI


# MCP improve forwards refined structured knowledge instead of dropping it


@pytest.mark.asyncio
async def test_mcp_improve_persists_refined_structured_knowledge() -> None:
    service, author_id, base = _service_with_base()
    await handle_contribute(
        service,
        author_id,
        {
            "solution_id": str(base.solution_id),
            "improved_content": (
                "Create the pool inside the running loop, await pool.close() before "
                "the loop stops, and never share a pool across loops — full fix"
            ),
            "root_cause_pattern": RC,
            "localization_cues": CUES,
            "verification": VERI,
            "reasoning": "adds root cause and repro",
        },
    )
    improved = [
        s
        for s in service._solutions.list_by_problem(base.problem_id)
        if s.parent_solution_id == base.solution_id
    ]
    assert improved, "improve did not create a child solution"
    sk = improved[-1]
    assert sk.root_cause_pattern == RC
    assert sk.localization_cues == CUES
    assert sk.verification == VERI


# Omitting structured knowledge inherits the parent's


def test_improve_without_structured_knowledge_inherits_parent() -> None:
    service, author_id, base = _service_with_base()
    body = SolutionImproveRequest(
        improved_content=(
            "Create the pool inside the running loop and await pool.close() before "
            "the loop stops so teardown never races the closed loop — clearer fix"
        ),
        reasoning="clarity",
    )
    agent = Agent(api_key_hash="h2", model_type="test", agent_id=author_id)
    result = rest_improve(base.solution_id, body, Response(), service, agent)
    improved = service._solutions.get(UUID(result.solution_id))
    assert improved is not None
    assert improved.root_cause_pattern == "old pattern"
    assert improved.localization_cues == ["old cue"]
