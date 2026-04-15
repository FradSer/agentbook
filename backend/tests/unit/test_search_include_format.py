"""Search response enrichment via `include=` and `format=` params."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.application.service import AgentbookService
from backend.domain.models import Agent, Outcome, Problem, Solution
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)


def _build_service() -> tuple[AgentbookService, dict]:
    agents = InMemoryAgentRepository()
    problems = InMemoryProblemRepository()
    solutions = InMemorySolutionRepository()
    outcomes = InMemoryOutcomeRepository()
    service = AgentbookService(
        agents=agents,
        problems=problems,
        solutions=solutions,
        outcomes=outcomes,
        research_cycles=InMemoryResearchCycleRepository(),
    )
    author = Agent(api_key_hash="h", model_type="claude-sonnet-4-5")
    agents.add(author)
    return service, {
        "agents": agents,
        "problems": problems,
        "solutions": solutions,
        "outcomes": outcomes,
        "author": author,
    }


def _make_problem(description: str, author_id) -> Problem:
    return Problem(
        problem_id=uuid4(),
        author_id=author_id,
        description=description,
        created_at=datetime.now(UTC),
        last_activity_at=datetime.now(UTC),
        review_status="approved",
    )


def _make_solution(
    problem_id,
    author_id,
    content: str,
    confidence: float = 0.8,
    parent_solution_id=None,
) -> Solution:
    return Solution(
        solution_id=uuid4(),
        problem_id=problem_id,
        author_id=author_id,
        content=content,
        confidence=confidence,
        created_at=datetime.now(UTC),
        review_status="approved",
        parent_solution_id=parent_solution_id,
    )


def test_concise_search_omits_enrichment_fields_by_default() -> None:
    service, ctx = _build_service()
    problem = _make_problem("postgres connection timeout", ctx["author"].agent_id)
    ctx["problems"].add(problem)
    ctx["solutions"].add(
        _make_solution(problem.problem_id, ctx["author"].agent_id, "restart pool")
    )

    payload = service.search_problems(query="postgres timeout", limit=5)
    row = payload["results"][0]
    assert "solutions" not in row or row["solutions"] is None
    assert "outcomes" not in row or row["outcomes"] is None
    assert "lineage" not in row or row["lineage"] is None


def test_include_solutions_returns_full_solution_list() -> None:
    service, ctx = _build_service()
    problem = _make_problem("flaky redis publish", ctx["author"].agent_id)
    ctx["problems"].add(problem)
    ctx["solutions"].add(
        _make_solution(
            problem.problem_id, ctx["author"].agent_id, "increase client timeout", 0.6
        )
    )
    ctx["solutions"].add(
        _make_solution(
            problem.problem_id, ctx["author"].agent_id, "disable pipelining", 0.9
        )
    )

    payload = service.search_problems(
        query="redis publish", limit=5, include={"solutions"}
    )
    row = payload["results"][0]
    assert row.get("solutions") is not None
    assert len(row["solutions"]) == 2


def test_include_outcomes_returns_outcomes_for_best_solution() -> None:
    service, ctx = _build_service()
    problem = _make_problem("kafka consumer rebalancing", ctx["author"].agent_id)
    ctx["problems"].add(problem)
    sol = _make_solution(
        problem.problem_id, ctx["author"].agent_id, "pin partition count", 0.9
    )
    ctx["solutions"].add(sol)
    for _ in range(2):
        ctx["outcomes"].add(
            Outcome(
                outcome_id=uuid4(),
                solution_id=sol.solution_id,
                reporter_id=ctx["author"].agent_id,
                success=True,
                created_at=datetime.now(UTC),
            )
        )

    payload = service.search_problems(
        query="kafka rebalancing", limit=5, include={"outcomes"}
    )
    row = payload["results"][0]
    assert row.get("outcomes") is not None
    assert len(row["outcomes"]) == 2


def test_include_lineage_returns_parent_chain() -> None:
    service, ctx = _build_service()
    problem = _make_problem("python asyncio deadlock", ctx["author"].agent_id)
    ctx["problems"].add(problem)
    parent = _make_solution(
        problem.problem_id, ctx["author"].agent_id, "wrap with to_thread", 0.5
    )
    ctx["solutions"].add(parent)
    child = _make_solution(
        problem.problem_id,
        ctx["author"].agent_id,
        "switch to anyio task group",
        0.95,
        parent_solution_id=parent.solution_id,
    )
    ctx["solutions"].add(child)

    payload = service.search_problems(
        query="asyncio deadlock", limit=5, include={"lineage"}
    )
    row = payload["results"][0]
    assert row.get("lineage") is not None
    assert len(row["lineage"]) == 2
    assert str(row["lineage"][0]["solution_id"]) == str(parent.solution_id)


def test_format_full_returns_untruncated_best_solution_content() -> None:
    service, ctx = _build_service()
    problem = _make_problem("long description matching query", ctx["author"].agent_id)
    ctx["problems"].add(problem)
    long_content = "step: " + ("x" * 400)
    ctx["solutions"].add(
        _make_solution(problem.problem_id, ctx["author"].agent_id, long_content, 0.9)
    )

    payload = service.search_problems(query="long description", limit=5, format="full")
    best = payload["results"][0]["best_solution"]
    assert best is not None
    assert best["content_preview"] == long_content


def test_format_concise_truncates_best_solution_content() -> None:
    service, ctx = _build_service()
    problem = _make_problem("another long query", ctx["author"].agent_id)
    ctx["problems"].add(problem)
    long_content = "x" * 500
    ctx["solutions"].add(
        _make_solution(problem.problem_id, ctx["author"].agent_id, long_content, 0.9)
    )

    payload = service.search_problems(query="another long", limit=5, format="concise")
    best = payload["results"][0]["best_solution"]
    assert best is not None
    assert len(best["content_preview"]) == 200


def test_include_supports_multiple_values() -> None:
    service, ctx = _build_service()
    problem = _make_problem("docker layer cache miss", ctx["author"].agent_id)
    ctx["problems"].add(problem)
    parent = _make_solution(
        problem.problem_id, ctx["author"].agent_id, "reorder COPY steps", 0.5
    )
    ctx["solutions"].add(parent)
    child = _make_solution(
        problem.problem_id,
        ctx["author"].agent_id,
        "mount buildkit cache",
        0.95,
        parent_solution_id=parent.solution_id,
    )
    ctx["solutions"].add(child)
    ctx["outcomes"].add(
        Outcome(
            outcome_id=uuid4(),
            solution_id=child.solution_id,
            reporter_id=ctx["author"].agent_id,
            success=True,
            created_at=datetime.now(UTC),
        )
    )

    payload = service.search_problems(
        query="docker layer cache",
        limit=5,
        include={"solutions", "outcomes", "lineage"},
    )
    row = payload["results"][0]
    assert row.get("solutions") is not None
    assert row.get("outcomes") is not None
    assert row.get("lineage") is not None
    assert len(row["solutions"]) == 2
    assert len(row["outcomes"]) == 1
    assert len(row["lineage"]) == 2
