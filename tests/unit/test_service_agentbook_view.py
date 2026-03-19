"""Unit tests for AgentbookService agentbook view and search (V3)."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.errors import NotFoundError
from app.domain.models import Problem, Solution


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
    from app.domain.models import Agent

    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(Agent(api_key_hash="test-hash", model_type="test", token_balance=100, agent_id=author_id))

    service = AgentbookService(
        agents=agents,
        transactions=InMemoryTokenTransactionRepository(),
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, author_id


def _create_approved_problem(service, author_id, description="ModuleNotFoundError in Docker Alpine"):
    p = service.create_problem(author_id=author_id, description=description)
    p.review_status = "approved"
    service._problems.update(p)
    return p


def _create_approved_solution(service, problem_id, author_id, content="Install with apk then pip"):
    s = service.create_solution(problem_id=problem_id, author_id=author_id, content=content)
    s.review_status = "approved"
    service._solutions.update(s)
    return s


def test_get_agentbook_returns_expected_keys():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    result = service.get_agentbook(p.problem_id)
    for key in ("problem_id", "description", "canonical_solution", "solution_history", "best_confidence", "solution_count"):
        assert key in result, f"Missing key: {key}"


def test_get_agentbook_solution_history_contains_approved_solution():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    s = _create_approved_solution(service, p.problem_id, author_id)
    result = service.get_agentbook(p.problem_id)
    sol_ids = [sol["solution_id"] if isinstance(sol, dict) else str(sol.solution_id) for sol in result["solution_history"]]
    assert str(s.solution_id) in str(sol_ids)


def test_get_agentbook_excludes_pending_solution():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    # Insert a pending solution directly (bypassing create_solution auto-approve)
    s = Solution(problem_id=p.problem_id, author_id=author_id, content="Pending solution content here", review_status=None)
    service._solutions.add(s)
    result = service.get_agentbook(p.problem_id)
    sol_ids = [sol["solution_id"] if isinstance(sol, dict) else str(sol.solution_id) for sol in result["solution_history"]]
    assert str(s.solution_id) not in str(sol_ids)


def test_get_agentbook_canonical_solution_when_set():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    canonical = _create_approved_solution(service, p.problem_id, author_id)
    p.canonical_solution_id = canonical.solution_id
    service._problems.update(p)
    result = service.get_agentbook(p.problem_id)
    assert result["canonical_solution"] is not None
    canon = result["canonical_solution"]
    canon_id = canon.get("solution_id") if isinstance(canon, dict) else str(canon.solution_id)
    assert str(canonical.solution_id) in str(canon_id)


def test_get_agentbook_canonical_none_when_not_set():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    result = service.get_agentbook(p.problem_id)
    assert result["canonical_solution"] is None


def test_get_agentbook_canonical_not_duplicated_in_history():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    canonical = _create_approved_solution(service, p.problem_id, author_id, content="Canonical solution content here")
    other = _create_approved_solution(service, p.problem_id, author_id, content="Alternative solution approach works differently")
    p.canonical_solution_id = canonical.solution_id
    service._problems.update(p)

    result = service.get_agentbook(p.problem_id)
    sol_ids = [sol.get("solution_id") if isinstance(sol, dict) else str(sol.solution_id) for sol in result["solution_history"]]
    assert str(canonical.solution_id) not in str(sol_ids)
    assert str(other.solution_id) in str(sol_ids)


def test_get_agentbook_raises_not_found_for_unknown_id():
    service, _ = _make_service()
    with pytest.raises(NotFoundError):
        service.get_agentbook(uuid4())


def test_search_returns_only_approved_problems():
    service, author_id = _make_service()
    approved = _create_approved_problem(service, author_id, description="ModuleNotFoundError numpy Docker Alpine pip")
    # Insert pending problem directly (bypassing create_problem auto-approve)
    pending = Problem(author_id=author_id, description="ModuleNotFoundError numpy Docker Alpine pip pending", review_status=None)
    service._problems.add(pending)

    results = service.search(query="ModuleNotFoundError numpy", limit=20)
    result_ids = [r.get("problem_id") if isinstance(r, dict) else str(r.problem_id) for r in results]
    assert str(approved.problem_id) in str(result_ids)
    assert str(pending.problem_id) not in str(result_ids)


def test_search_result_includes_best_solution_fields():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id, description="ConnectionRefusedError redis Docker compose setup issue")
    s = _create_approved_solution(service, p.problem_id, author_id, content="Run redis container with correct ports")

    results = service.search(query="ConnectionRefusedError redis", limit=5)
    assert len(results) >= 1
    r = results[0]
    best = r.get("best_solution") if isinstance(r, dict) else None
    assert best is not None
    for key in ("confidence", "content_preview"):
        assert key in best, f"Missing key in best_solution: {key}"
