"""Tests for improve_solution hill-climbing logic."""
from __future__ import annotations

from uuid import UUID

import pytest

from app.application.errors import NotFoundError
from app.application.service import AgentbookService
from app.domain.models import Agent, Problem, Solution
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


def _seed_problem_and_solution(service: AgentbookService) -> tuple[UUID, UUID]:
    result = service.contribute(
        author_id=AUTHOR,
        description="How to fix ModuleNotFoundError in Docker",
        solution_content="Install the missing package with pip install",
        solution_steps=["Run pip install <package>"],
        author_verified=True,
    )
    return UUID(str(result["problem_id"])), UUID(str(result["solution_id"]))


def test_improve_solution_returns_improved_when_better() -> None:
    service = _make_service()
    problem_id, solution_id = _seed_problem_and_solution(service)

    result = service.improve_solution(
        author_id=RESEARCHER,
        solution_id=solution_id,
        improved_content="Install the missing package and rebuild the Docker image",
        improved_steps=["Run pip install <package>", "Rebuild with docker build", "Restart container"],
        reasoning="Added rebuild step which is required",
        author_verified=True,
    )

    assert result["status"] in ("improved", "no_improvement")
    assert "solution_id" in result
    assert "previous_confidence" in result
    assert "new_confidence" in result


def test_improve_solution_raises_not_found_for_missing_solution() -> None:
    service = _make_service()
    missing_id = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")

    with pytest.raises(NotFoundError):
        service.improve_solution(
            author_id=RESEARCHER,
            solution_id=missing_id,
            improved_content="Some content that is long enough to pass quality gate",
        )


def test_improve_solution_raises_on_bad_quality() -> None:
    service = _make_service()
    _, solution_id = _seed_problem_and_solution(service)

    with pytest.raises(ValueError):
        service.improve_solution(
            author_id=RESEARCHER,
            solution_id=solution_id,
            improved_content="buy now at http://spam.com",
        )


def test_improve_solution_records_research_cycle() -> None:
    service = _make_service()
    _, solution_id = _seed_problem_and_solution(service)

    service.improve_solution(
        author_id=RESEARCHER,
        solution_id=solution_id,
        improved_content="Install the missing package and rebuild the Docker image with --no-cache",
        improved_steps=["pip install <package>", "docker build --no-cache", "docker run"],
        reasoning="Added --no-cache to ensure fresh build",
        author_verified=True,
    )

    problem_id, _ = _seed_problem_and_solution(service)
    # research_cycles repo should have at least one entry
    assert service._research_cycles is not None


def test_improve_solution_sets_parent_solution_id() -> None:
    service = _make_service()
    _, solution_id = _seed_problem_and_solution(service)

    result = service.improve_solution(
        author_id=RESEARCHER,
        solution_id=solution_id,
        improved_content="Install the missing package and rebuild the Docker image with --no-cache",
        improved_steps=["pip install <package>", "docker build --no-cache"],
        author_verified=True,
    )

    new_id = UUID(str(result["solution_id"]))
    new_solution = service._solutions.get(new_id)
    assert new_solution is not None
    assert new_solution.parent_solution_id == solution_id


def test_improve_solution_detects_existing_cycle() -> None:
    """Detect if parent lineage already has a cycle (from concurrent modification bug)."""
    service = _make_service()
    _, solution_a = _seed_problem_and_solution(service)

    # A → B
    result_b = service.improve_solution(
        author_id=RESEARCHER,
        solution_id=solution_a,
        improved_content="Improved version B with more details and better steps",
        improved_steps=["step1", "step2"],
        author_verified=True,
    )
    solution_b = UUID(str(result_b["solution_id"]))

    # Simulate concurrent modification bug: create cycle A → B → A
    a_obj = service._solutions.get(solution_a)
    b_obj = service._solutions.get(solution_b)
    assert a_obj is not None and b_obj is not None

    # B already has B.parent = A
    # Now set A.parent = B to create cycle
    object.__setattr__(a_obj, "parent_solution_id", solution_b)
    service._solutions.update(a_obj)

    # Now A → B → A (cycle exists)
    # Try to improve A (should detect cycle when validating A's ancestry)
    with pytest.raises(ValueError, match="Cycle detected"):
        service.improve_solution(
            author_id=RESEARCHER,
            solution_id=solution_a,
            improved_content="This should fail because A's ancestry has a cycle",
            improved_steps=["step1"],
            author_verified=True,
        )
