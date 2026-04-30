"""Unit tests for AgentbookService problem/solution CRUD."""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.domain.models import Agent, Problem, Solution


def _make_service():
    from backend.application.service import AgentbookService
    from backend.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
    )

    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(
        Agent(
            api_key_hash="test-hash",
            model_type="test-model",
            agent_id=author_id,
        )
    )

    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, author_id


def test_create_problem_returns_problem_auto_approved():
    service, author_id = _make_service()
    problem = service.create_problem(
        author_id=author_id,
        description="ModuleNotFoundError importing numpy in Docker Alpine container",
    )
    assert isinstance(problem, Problem)
    assert problem.review_status == "approved"
    assert problem.author_id == author_id


def test_create_problem_raises_value_error_when_gate_rejects():
    service, author_id = _make_service()
    with pytest.raises(ValueError):
        service.create_problem(author_id=author_id, description="help")


def test_create_solution_returns_solution_with_default_confidence():
    service, author_id = _make_service()
    problem = service.create_problem(
        author_id=author_id,
        description="ModuleNotFoundError importing numpy in Docker Alpine container",
    )
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Install numpy with apk dependencies first then pip install",
    )
    assert isinstance(solution, Solution)
    assert solution.confidence == 0.3
    assert solution.review_status == "approved"


def test_create_solution_increments_problem_solution_count():
    service, author_id = _make_service()
    problem = service.create_problem(
        author_id=author_id,
        description="ModuleNotFoundError importing numpy in Docker Alpine container",
    )
    problem.review_status = "approved"
    service._problems.update(problem)

    assert problem.solution_count == 0
    service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Install numpy with apk dependencies first then pip install",
    )
    updated = service._problems.get(problem.problem_id)
    assert updated.solution_count == 1


def test_create_solution_raises_when_gate_rejects_content():
    service, author_id = _make_service()
    problem = service.create_problem(
        author_id=author_id,
        description="ModuleNotFoundError importing numpy in Docker Alpine container",
    )
    problem.review_status = "approved"
    service._problems.update(problem)

    with pytest.raises(ValueError):
        service.create_solution(
            problem_id=problem.problem_id,
            author_id=author_id,
            content="x",  # too short
        )


def test_contribute_with_solution_returns_knowledge_created():
    service, author_id = _make_service()
    result = service.contribute(
        author_id=author_id,
        description="ModuleNotFoundError importing numpy in Docker Alpine container",
        solution_content="Install numpy with apk dependencies first then pip install",
    )
    assert result["status"] == "knowledge_created"
    assert "problem_id" in result
    assert "solution_id" in result


def test_contribute_without_solution_returns_problem_created():
    service, author_id = _make_service()
    result = service.contribute(
        author_id=author_id,
        description="Segmentation fault using multiprocessing with fork on macOS",
    )
    assert result["status"] == "problem_created"
    assert "problem_id" in result


def test_contribute_solution_to_existing_approved_problem():
    service, author_id = _make_service()
    # Create and approve a problem
    problem = service.create_problem(
        author_id=author_id,
        description="ModuleNotFoundError importing numpy in Docker Alpine container",
    )
    problem.review_status = "approved"
    service._problems.update(problem)

    result = service.contribute(
        author_id=author_id,
        description="ModuleNotFoundError importing numpy in Docker Alpine container",
        solution_content="Install numpy with apk dependencies first then pip install",
        problem_id=problem.problem_id,
    )
    assert result["status"] in ("knowledge_created", "solution_added")
    updated = service._problems.get(problem.problem_id)
    assert updated.solution_count >= 1
