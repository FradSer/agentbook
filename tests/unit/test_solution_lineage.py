"""Tests for solution lineage tracking."""
from __future__ import annotations

from uuid import UUID

import pytest

from app.application.errors import NotFoundError
from app.application.service import AgentbookService
from app.domain.models import Agent
from app.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryCommentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
    InMemoryThreadRepository,
    InMemoryTokenTransactionRepository,
    InMemoryVoteRepository,
)

AUTHOR = UUID("00000000-0000-0000-0000-000000000001")
RESEARCHER = UUID("00000000-0000-0000-0000-000000000002")


def _make_service() -> AgentbookService:
    agents = InMemoryAgentRepository()
    agents.add(Agent(api_key_hash="h1", model_type="test", token_balance=100, agent_id=AUTHOR))
    agents.add(Agent(api_key_hash="h2", model_type="test", token_balance=100, agent_id=RESEARCHER))
    return AgentbookService(
        agents=agents,
        threads=InMemoryThreadRepository(),
        comments=InMemoryCommentRepository(),
        votes=InMemoryVoteRepository(),
        transactions=InMemoryTokenTransactionRepository(),
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )


def test_lineage_single_solution() -> None:
    service = _make_service()
    result = service.contribute(
        author_id=AUTHOR,
        description="How to fix ModuleNotFoundError in Docker",
        solution_content="Install the missing package with pip install",
        solution_steps=["Run pip install <package>"],
    )
    solution_id = UUID(str(result["solution_id"]))

    lineage = service.get_solution_lineage(solution_id)
    assert len(lineage) == 1
    assert str(lineage[0]["solution_id"]) == str(solution_id)


def test_lineage_two_generations() -> None:
    service = _make_service()
    result = service.contribute(
        author_id=AUTHOR,
        description="How to fix ModuleNotFoundError in Docker",
        solution_content="Install the missing package with pip install",
        solution_steps=["Run pip install <package>"],
    )
    solution_id = UUID(str(result["solution_id"]))

    improved = service.improve_solution(
        author_id=RESEARCHER,
        solution_id=solution_id,
        improved_content="Install the missing package and rebuild the Docker image",
        improved_steps=["pip install <package>", "docker build", "docker run"],
        author_verified=True,
    )
    new_id = UUID(str(improved["solution_id"]))

    lineage = service.get_solution_lineage(new_id)
    assert len(lineage) == 2
    assert str(lineage[0]["solution_id"]) == str(solution_id)
    assert str(lineage[1]["solution_id"]) == str(new_id)


def test_lineage_raises_not_found_for_missing() -> None:
    service = _make_service()
    with pytest.raises(NotFoundError):
        service.get_solution_lineage(UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"))
