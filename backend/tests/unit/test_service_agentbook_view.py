"""Unit tests for AgentbookService agentbook view and search."""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.application.errors import NotFoundError
from backend.domain.models import Problem, Solution


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


def _create_approved_problem(
    service, author_id, description="ModuleNotFoundError in Docker Alpine"
):
    p = service.create_problem(author_id=author_id, description=description)
    p.review_status = "approved"
    service._problems.update(p)
    return p


def _create_approved_solution(
    service, problem_id, author_id, content="Install with apk then pip"
):
    s = service.create_solution(
        problem_id=problem_id, author_id=author_id, content=content
    )
    s.review_status = "approved"
    service._solutions.update(s)
    return s


def test_get_agentbook_returns_expected_keys():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    result = service.get_agentbook(p.problem_id)
    for key in (
        "problem_id",
        "description",
        "canonical_solution",
        "solution_history",
        "best_confidence",
        "solution_count",
    ):
        assert key in result, f"Missing key: {key}"


def test_get_agentbook_solution_history_contains_approved_solution():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    s = _create_approved_solution(service, p.problem_id, author_id)
    result = service.get_agentbook(p.problem_id)
    sol_ids = [
        sol["solution_id"] if isinstance(sol, dict) else str(sol.solution_id)
        for sol in result["solution_history"]
    ]
    assert str(s.solution_id) in str(sol_ids)


def test_get_agentbook_excludes_pending_solution():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    # Insert a pending solution directly (bypassing create_solution auto-approve)
    s = Solution(
        problem_id=p.problem_id,
        author_id=author_id,
        content="Pending solution content here",
        review_status=None,
    )
    service._solutions.add(s)
    result = service.get_agentbook(p.problem_id)
    sol_ids = [
        sol["solution_id"] if isinstance(sol, dict) else str(sol.solution_id)
        for sol in result["solution_history"]
    ]
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
    canon_id = (
        canon.get("solution_id") if isinstance(canon, dict) else str(canon.solution_id)
    )
    assert str(canonical.solution_id) in str(canon_id)


def test_get_agentbook_canonical_none_when_not_set():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    result = service.get_agentbook(p.problem_id)
    assert result["canonical_solution"] is None


def test_get_agentbook_canonical_not_duplicated_in_history():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    canonical = _create_approved_solution(
        service, p.problem_id, author_id, content="Canonical solution content here"
    )
    other = _create_approved_solution(
        service,
        p.problem_id,
        author_id,
        content="Alternative solution approach works differently",
    )
    p.canonical_solution_id = canonical.solution_id
    service._problems.update(p)

    result = service.get_agentbook(p.problem_id)
    sol_ids = [
        sol.get("solution_id") if isinstance(sol, dict) else str(sol.solution_id)
        for sol in result["solution_history"]
    ]
    assert str(canonical.solution_id) not in str(sol_ids)
    assert str(other.solution_id) in str(sol_ids)


def test_get_agentbook_raises_not_found_for_unknown_id():
    service, _ = _make_service()
    with pytest.raises(NotFoundError):
        service.get_agentbook(uuid4())


def test_search_returns_only_approved_problems():
    service, author_id = _make_service()
    approved = _create_approved_problem(
        service, author_id, description="ModuleNotFoundError numpy Docker Alpine pip"
    )
    # Insert pending problem directly (bypassing create_problem auto-approve)
    pending = Problem(
        author_id=author_id,
        description="ModuleNotFoundError numpy Docker Alpine pip pending",
        review_status=None,
    )
    service._problems.add(pending)

    payload = service.search_problems(query="ModuleNotFoundError numpy", limit=20)
    result_ids = [r["problem_id"] for r in payload["results"]]
    assert str(approved.problem_id) in str(result_ids)
    assert str(pending.problem_id) not in str(result_ids)


def test_search_result_includes_best_solution_fields():
    service, author_id = _make_service()
    p = _create_approved_problem(
        service,
        author_id,
        description="ConnectionRefusedError redis Docker compose setup issue",
    )
    _create_approved_solution(
        service,
        p.problem_id,
        author_id,
        content="Run redis container with correct ports",
    )

    payload = service.search_problems(query="ConnectionRefusedError redis", limit=5)
    assert len(payload["results"]) >= 1
    r = payload["results"][0]
    best = r.get("best_solution")
    assert best is not None
    for key in ("confidence", "content_preview"):
        assert key in best, f"Missing key in best_solution: {key}"


def test_search_prioritizes_exact_error_signature_match():
    service, author_id = _make_service()
    target = _create_approved_problem(
        service,
        author_id,
        description="FastAPI requests intermittently hang under database load",
    )
    target.error_signature = (
        "TimeoutError: QueuePool limit of size 5 overflow 10 reached"
    )
    service._problems.update(target)
    _create_approved_solution(
        service,
        target.problem_id,
        author_id,
        content="Close sessions with a dependency finalizer after each request",
    )

    payload = service.search_problems(query="QueuePool", limit=5)

    assert payload["results"][0]["problem_id"] == str(target.problem_id)
    assert payload["results"][0]["match_quality"] == "exact"
    assert "error_signature" in payload["results"][0]["match_reasons"]


def test_search_suppresses_low_quality_keyword_overlap():
    service, author_id = _make_service()
    _create_approved_problem(
        service,
        author_id,
        description=(
            "Docker container completes pip install but fails importing numpy "
            "on Alpine at runtime"
        ),
    )

    payload = service.search_problems(
        query="Corepack pnpm install packageManager mismatch in CI",
        limit=5,
    )

    assert payload["results"] == []
    assert payload["total"] == 0
    assert payload["no_good_match"] is True


# --- Progressive disclosure fields ---


def test_get_agentbook_includes_outcome_summary_with_data():
    """Two distinct reporters yield two outcome rows.

    Pre-v6 the same author could report twice and produce two rows;
    under v6 the second call upserts. The summary shape is unchanged —
    just use distinct reporters to express the original intent.
    """
    from backend.domain.models import Agent

    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    s = _create_approved_solution(service, p.problem_id, author_id)
    bob_id = uuid4()
    carol_id = uuid4()
    service._agents.add(
        Agent(api_key_hash="bob-hash", model_type="test", agent_id=bob_id)
    )
    service._agents.add(
        Agent(api_key_hash="carol-hash", model_type="test", agent_id=carol_id)
    )
    service.report_outcome(
        solution_id=s.solution_id,
        reporter_id=bob_id,
        success=True,
        notes="Worked",
    )
    service.report_outcome(
        solution_id=s.solution_id,
        reporter_id=carol_id,
        success=False,
        notes="Failed on Alpine",
    )
    result = service.get_agentbook(p.problem_id)
    summary = result["outcome_summary"]
    assert summary["total"] == 2
    assert summary["successes"] == 1
    assert summary["failures"] == 1
    assert "Failed on Alpine" in summary["recent_failure_notes"]


def test_get_agentbook_outcome_summary_empty_when_no_outcomes():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    _create_approved_solution(service, p.problem_id, author_id)
    result = service.get_agentbook(p.problem_id)
    summary = result["outcome_summary"]
    assert summary["total"] == 0
    assert summary["recent_failure_notes"] == []


def test_get_agentbook_includes_research_summary_with_cycles():
    from backend.domain.models import ResearchCycle

    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    _create_approved_solution(service, p.problem_id, author_id)
    service._research_cycles.add(
        ResearchCycle(
            problem_id=p.problem_id,
            researcher_id=author_id,
            proposed_solution_id=None,
            previous_best_confidence=0.3,
            new_confidence=0.3,
            status="no_improvement",
            reasoning="No better approach found",
        )
    )
    result = service.get_agentbook(p.problem_id)
    summary = result["research_summary"]
    assert summary["total_cycles"] == 1
    assert summary["last_status"] == "no_improvement"
    assert summary["consecutive_no_improvement"] == 1
    assert summary["last_researched_at"] is not None


def test_get_agentbook_research_summary_empty_when_no_cycles():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    result = service.get_agentbook(p.problem_id)
    summary = result["research_summary"]
    assert summary["total_cycles"] == 0
    assert summary["last_status"] is None
    assert summary["consecutive_no_improvement"] == 0


def test_get_agentbook_includes_is_being_researched():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    result = service.get_agentbook(p.problem_id)
    assert result["is_being_researched"] is False


def test_get_agentbook_outcome_summary_uses_synthesized_canonical_sources():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    first = _create_approved_solution(
        service, p.problem_id, author_id, content="First approach"
    )
    second = _create_approved_solution(
        service, p.problem_id, author_id, content="Second approach"
    )
    service.report_outcome(
        solution_id=first.solution_id,
        reporter_id=author_id,
        success=True,
        notes="Worked in CI",
    )
    service.report_outcome(
        solution_id=second.solution_id,
        reporter_id=author_id,
        success=False,
        notes="Failed on macOS",
    )

    service.synthesize_solutions(
        p.problem_id,
        synthesized_content="Canonical synthesis of both approaches",
    )

    result = service.get_agentbook(p.problem_id)
    summary = result["outcome_summary"]
    provenance = result["canonical_solution"]["confidence_provenance"]

    assert result["canonical_solution"]["outcome_count"] == 2
    assert summary["total"] == 2
    assert summary["successes"] == 1
    assert summary["failures"] == 1
    assert "Failed on macOS" in summary["recent_failure_notes"]

    # Confidence provenance tracks inherited outcomes from source solutions
    assert provenance["source"] == "synthesized_sources"
    assert provenance["direct_outcomes"] == 0
    assert provenance["inherited_outcomes"] == 2
    assert provenance["successes"] == 1
    assert provenance["failures"] == 1
    assert set(provenance["source_solution_ids"]) == {
        str(first.solution_id),
        str(second.solution_id),
    }
