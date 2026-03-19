"""Unit tests for AgentbookService unified review lifecycle (V3)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.errors import NotFoundError
from app.domain.models import Agent, Problem, Solution


def _make_service():
    from app.application.service import AgentbookService
    from app.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
        InMemoryTokenTransactionRepository,
    )

    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(
        Agent(api_key_hash="test-hash", model_type="test", token_balance=100, agent_id=author_id)
    )
    service = AgentbookService(
        agents=agents,
        transactions=InMemoryTokenTransactionRepository(),
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, author_id


def _create_approved_problem(service, author_id):
    p = service.create_problem(
        author_id=author_id,
        description="ModuleNotFoundError importing numpy in Docker Alpine container",
    )
    p.review_status = "approved"
    service._problems.update(p)
    return p


def test_update_review_approves_problem():
    service, author_id = _make_service()
    p = service.create_problem(
        author_id=author_id,
        description="ModuleNotFoundError importing numpy in Docker Alpine container",
    )
    service.update_review(
        content_id=p.problem_id,
        status="approved",
        score=1.0,
        reviewed_at=datetime.now(UTC),
    )
    updated = service._problems.get(p.problem_id)
    assert updated.review_status == "approved"
    assert updated.review_score == 1.0


def test_update_review_rejects_solution():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    s = service.create_solution(
        problem_id=p.problem_id,
        author_id=author_id,
        content="Install numpy with apk dependencies first then pip install",
    )
    service.update_review(
        content_id=s.solution_id,
        status="rejected",
        score=0.0,
        reviewed_at=datetime.now(UTC),
    )
    updated = service._solutions.get(s.solution_id)
    assert updated.review_status == "rejected"


def test_update_review_unknown_id_raises_not_found():
    service, _ = _make_service()
    with pytest.raises(NotFoundError):
        service.update_review(
            content_id=uuid4(),
            status="approved",
            score=1.0,
            reviewed_at=datetime.now(UTC),
        )


def test_delete_content_removes_problem_and_solutions():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    s = service.create_solution(
        problem_id=p.problem_id,
        author_id=author_id,
        content="Install numpy with apk dependencies first then pip install",
    )
    service.delete_content(p.problem_id)
    assert service._problems.get(p.problem_id) is None
    assert service._solutions.get(s.solution_id) is None


def test_delete_content_removes_solution_decrements_count():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    s = service.create_solution(
        problem_id=p.problem_id,
        author_id=author_id,
        content="Install numpy with apk dependencies first then pip install",
    )
    assert service._problems.get(p.problem_id).solution_count == 1
    service.delete_content(s.solution_id)
    assert service._solutions.get(s.solution_id) is None
    assert service._problems.get(p.problem_id).solution_count == 0


def test_delete_content_unknown_id_raises_not_found():
    service, _ = _make_service()
    with pytest.raises(NotFoundError):
        service.delete_content(uuid4())


def test_get_unreviewed_problems_returns_pending():
    service, author_id = _make_service()
    # Insert directly with review_status=None to simulate content awaiting review
    p = Problem(author_id=author_id, description="pending problem", review_status=None)
    service._problems.add(p)
    results = service.get_unreviewed_problems(limit=10)
    ids = [r.problem_id for r in results]
    assert p.problem_id in ids


def test_get_unreviewed_problems_excludes_approved():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    results = service.get_unreviewed_problems(limit=10)
    ids = [r.problem_id for r in results]
    assert p.problem_id not in ids


def test_get_unreviewed_solutions_returns_pending():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    # Insert directly with review_status=None to simulate content awaiting review
    s = Solution(problem_id=p.problem_id, author_id=author_id,
                 content="pending solution content", review_status=None)
    service._solutions.add(s)
    results = service.get_unreviewed_solutions(limit=10)
    ids = [r.solution_id for r in results]
    assert s.solution_id in ids


def test_list_problems_returns_only_approved():
    service, author_id = _make_service()
    # Insert a pending problem directly (bypassing create_problem auto-approve)
    pending = Problem(author_id=author_id, description="pending problem", review_status=None)
    service._problems.add(pending)
    approved = _create_approved_problem(service, author_id)
    results = service.list_problems(limit=10)
    ids = [r["problem_id"] if isinstance(r, dict) else str(r.problem_id) for r in results]
    assert str(approved.problem_id) in str(ids)
    assert str(pending.problem_id) not in str(ids)
