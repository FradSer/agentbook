"""Unit tests for AgentbookService hill-climbing and auto research."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4


def _make_service():
    from backend.application.service import AgentbookService
    from backend.domain.models import Agent
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
            model_type="test",
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


def _setup_approved_problem_and_solution(service, author_id):
    p = service.create_problem(
        author_id=author_id,
        description="ModuleNotFoundError importing numpy in Docker Alpine container setup environment",
    )
    p.review_status = "approved"
    service._problems.update(p)
    s = service.create_solution(
        problem_id=p.problem_id,
        author_id=author_id,
        content="Install numpy with apk add musl-dev gcc then pip install numpy in Docker Alpine",
    )
    s.review_status = "approved"
    s.confidence = 0.4
    service._solutions.update(s)
    return p, s


def test_improve_solution_accepted_when_strictly_higher_confidence():
    service, author_id = _make_service()
    p, s = _setup_approved_problem_and_solution(service, author_id)
    s.confidence = 0.25
    service._solutions.update(s)

    result = service.improve_solution(
        solution_id=s.solution_id,
        improved_content="Install numpy with apk add musl-dev gcc python3-dev then pip install numpy --no-cache-dir in Alpine",
        reasoning="Added python3-dev dependency which is also required",
    )
    assert result["status"] == "improved"


def test_improve_solution_rejected_when_equal_confidence():
    service, author_id = _make_service()
    p, s = _setup_approved_problem_and_solution(service, author_id)
    # Set outcome_count > 0 so the normal confidence path fires (not cold-start).
    # New solution starts at baseline 0.3, existing at 0.4, so equal fails.
    s.outcome_count = 1
    service._solutions.update(s)

    result = service.improve_solution(
        solution_id=s.solution_id,
        improved_content="Install numpy with apk add musl-dev gcc then pip install numpy equals same",
        reasoning="Same confidence",
    )
    assert result["status"] == "no_improvement"
    assert result["reason"] == "no_improvement"
    assert result["next_action"] == "collect_outcome_or_verify"


def test_improve_solution_rejected_content_regression_too_short():
    service, author_id = _make_service()
    p, s = _setup_approved_problem_and_solution(service, author_id)
    # original content is ~80 chars; provide content < 50% of that
    short_content = "pip fix"  # 7 chars — less than 50% of original

    result = service.improve_solution(
        solution_id=s.solution_id,
        improved_content=short_content,
        reasoning="Shorter fix",
    )
    assert result["status"] == "no_improvement"
    assert result["reason"] == "content_regression"
    assert result["next_action"] == "revise_content"


def test_improve_solution_rejected_content_bloat():
    service, author_id = _make_service()
    p, s = _setup_approved_problem_and_solution(service, author_id)
    s.confidence = 0.5
    s.outcome_count = 1
    service._solutions.update(s)

    # Content > 2x original length. New solution starts at baseline 0.3,
    # so confidence gain is 0.3 - 0.5 = negative. Bloat check fires because
    # 0.3 <= 0.5 + 0.05.
    bloated_content = (
        "Install numpy with apk add musl-dev gcc then pip install numpy in Docker Alpine "
        * 10
    )

    result = service.improve_solution(
        solution_id=s.solution_id,
        improved_content=bloated_content,
        reasoning="Bloated with minimal gain",
    )
    assert result["status"] == "no_improvement"
    assert result["reason"] == "content_bloat"
    assert result["next_action"] == "revise_content"


def test_improve_solution_valid_lineage_proceeds():
    service, author_id = _make_service()
    p, s1 = _setup_approved_problem_and_solution(service, author_id)

    # Create sol-2 with parent=sol-1
    s2 = service.create_solution(
        problem_id=p.problem_id,
        author_id=author_id,
        content="Improved install steps for numpy in Docker Alpine with explicit deps and cache flags here",
        parent_solution_id=s1.solution_id,
    )
    s2.review_status = "approved"
    s2.confidence = 0.25
    service._solutions.update(s2)

    # Now improve sol-2 with parent=sol-2 (creates sol-3)
    result = service.improve_solution(
        solution_id=s2.solution_id,
        improved_content="Best install steps for numpy in Docker Alpine with all explicit deps and no-cache flags included",
        reasoning="Added author verification and full dep list",
    )
    # Should proceed (no cycle: sol-3 -> sol-2 -> sol-1 -> null)
    assert result["status"] in ("improved", "no_improvement")


def test_synthesize_solutions_creates_canonical():
    service, author_id = _make_service()
    p = service.create_problem(
        author_id=author_id,
        description="ConnectionRefusedError redis Docker compose networking setup configuration",
    )
    p.review_status = "approved"
    service._problems.update(p)

    # Create 10 approved solutions
    for i in range(10):
        s = service.create_solution(
            problem_id=p.problem_id,
            author_id=author_id,
            content=f"Solution variant {i}: Run redis container with specific ports and network config settings here",
        )
        s.review_status = "approved"
        service._solutions.update(s)

    result = service.synthesize_solutions(p.problem_id)
    updated_problem = service._problems.get(p.problem_id)
    assert updated_problem.canonical_solution_id is not None
    assert result is not None


def test_find_research_candidates_excludes_recently_researched():
    service, author_id = _make_service()
    from backend.domain.models import ResearchCycle

    p = service.create_problem(
        author_id=author_id,
        description="ImportError numpy wheels building Docker Alpine container issue recent",
    )
    p.review_status = "approved"
    service._problems.update(p)

    # Create a recent research cycle (1 hour ago)
    cycle = ResearchCycle(
        problem_id=p.problem_id,
        researcher_id=author_id,
        proposed_solution_id=None,
        status="completed",
    )
    cycle.created_at = datetime.now(UTC) - timedelta(hours=1)
    service._research_cycles.add(cycle)

    candidates = service.find_research_candidates(limit=10, cooldown_hours=6)
    candidate_ids = [
        c.problem_id if hasattr(c, "problem_id") else c["problem_id"]
        for c in candidates
    ]
    assert p.problem_id not in candidate_ids


def test_find_research_candidates_includes_old_research():
    service, author_id = _make_service()
    from backend.domain.models import ResearchCycle

    p = service.create_problem(
        author_id=author_id,
        description="SyntaxError unexpected token JavaScript webpack bundler old research cycle test",
    )
    p.review_status = "approved"
    service._problems.update(p)

    # Research cycle more than 6 hours ago
    cycle = ResearchCycle(
        problem_id=p.problem_id,
        researcher_id=author_id,
        proposed_solution_id=None,
        status="completed",
    )
    cycle.created_at = datetime.now(UTC) - timedelta(hours=8)
    service._research_cycles.add(cycle)

    candidates = service.find_research_candidates(limit=10, cooldown_hours=6)
    candidate_ids = [
        c.problem_id if hasattr(c, "problem_id") else c["problem_id"]
        for c in candidates
    ]
    assert p.problem_id in candidate_ids


def test_get_solution_lineage_returns_chain():
    service, author_id = _make_service()
    p, s1 = _setup_approved_problem_and_solution(service, author_id)

    s2 = service.create_solution(
        problem_id=p.problem_id,
        author_id=author_id,
        content="Improved solution v2 with added dependency for Docker Alpine numpy install steps",
        parent_solution_id=s1.solution_id,
    )

    lineage = service.get_solution_lineage(s2.solution_id)
    assert lineage is not None
    assert len(lineage) >= 2
