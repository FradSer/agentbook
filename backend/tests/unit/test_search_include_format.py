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


def test_include_solutions_exposes_steps_per_solution() -> None:
    service, ctx = _build_service()
    problem = _make_problem("nginx 502 upstream timeout", ctx["author"].agent_id)
    ctx["problems"].add(problem)
    sol = _make_solution(
        problem.problem_id, ctx["author"].agent_id, "raise proxy_read_timeout", 0.9
    )
    sol.steps = ["Open nginx.conf", "Set proxy_read_timeout 120s"]
    ctx["solutions"].add(sol)

    payload = service.search_problems(
        query="nginx 502 timeout", limit=5, include={"solutions"}
    )
    sols = payload["results"][0]["solutions"]
    assert sols[0]["steps"] == ["Open nginx.conf", "Set proxy_read_timeout 120s"]


def test_structured_knowledge_served_in_best_solution_and_include() -> None:
    service, ctx = _build_service()
    problem = _make_problem("posify drops assumptions", ctx["author"].agent_id)
    ctx["problems"].add(problem)
    sol = _make_solution(
        problem.problem_id, ctx["author"].agent_id, "preserve assumptions", 0.9
    )
    sol.root_cause_pattern = "Dummy(positive=True) drops the symbol's other assumptions"
    sol.localization_cues = ["sympy/simplify/simplify.py: posify Dummy(...)"]
    sol.verification = [{"command": "python -c '...'", "expected": "True"}]
    ctx["solutions"].add(sol)

    payload = service.search_problems(
        query="posify assumptions", limit=5, include={"solutions"}
    )
    row = payload["results"][0]
    served = row["solutions"][0]
    assert served["root_cause_pattern"].startswith("Dummy(positive=True)")
    assert served["localization_cues"] == [
        "sympy/simplify/simplify.py: posify Dummy(...)"
    ]
    assert served["verification"][0]["expected"] == "True"
    best = row["best_solution"]
    assert best["root_cause_pattern"].startswith("Dummy(positive=True)")
    assert best["localization_cues"] and best["verification"]


def test_contribute_persists_and_serves_structured_knowledge() -> None:
    service, ctx = _build_service()
    res = service.contribute(
        author_id=ctx["author"].agent_id,
        description="celery worker hangs on SIGTERM during warm shutdown",
        solution_content="handle SIGTERM to drain tasks",
        solution_steps=["trap SIGTERM", "drain then exit"],
        solution_root_cause_pattern="warm_shutdown ignores SIGTERM, blocks on prefetch",
        solution_localization_cues=["celery/worker/consumer.py: on_close"],
        solution_verification=[{"command": "pytest -k sigterm", "expected": "passed"}],
    )
    assert res["solution_id"] is not None

    payload = service.search_problems(
        query="celery SIGTERM warm shutdown", limit=5, include={"solutions"}
    )
    best = payload["results"][0]["best_solution"]
    assert best["root_cause_pattern"].startswith("warm_shutdown ignores SIGTERM")
    assert best["localization_cues"] == ["celery/worker/consumer.py: on_close"]
    assert best["verification"][0]["expected"] == "passed"


def test_improve_inherits_parent_structured_knowledge() -> None:
    service, ctx = _build_service()
    problem = _make_problem("pg pool exhausted under load", ctx["author"].agent_id)
    ctx["problems"].add(problem)
    parent = _make_solution(
        problem.problem_id, ctx["author"].agent_id, "raise the pool size", 0.5
    )
    parent.root_cause_pattern = "pool max below peak concurrency"
    parent.localization_cues = ["db.py: create_pool"]
    parent.verification = [{"command": "pytest -k pool", "expected": "passed"}]
    ctx["solutions"].add(parent)

    service.improve_solution(
        solution_id=parent.solution_id,
        improved_content="raise the pool size and add overflow handling for spikes",
        author_id=ctx["author"].agent_id,
    )

    child = next(
        s
        for s in service._solutions.list_by_problem(problem.problem_id)
        if s.parent_solution_id == parent.solution_id
    )
    assert child.root_cause_pattern == "pool max below peak concurrency"
    assert child.localization_cues == ["db.py: create_pool"]
    assert child.verification[0]["command"] == "pytest -k pool"


def test_synthesis_carries_structured_knowledge_forward() -> None:
    service, ctx = _build_service()
    problem = _make_problem("flaky ssl handshake after fork", ctx["author"].agent_id)
    ctx["problems"].add(problem)
    s1 = _make_solution(
        problem.problem_id, ctx["author"].agent_id, "pin the TLS version", 0.6
    )
    s1.root_cause_pattern = "ssl session reused across forked workers"
    s1.localization_cues = ["ssl_ctx.py: wrap_socket"]
    s1.verification = [{"command": "pytest -k tls", "expected": "passed"}]
    ctx["solutions"].add(s1)
    s2 = _make_solution(
        problem.problem_id, ctx["author"].agent_id, "disable the session cache", 0.9
    )
    s2.localization_cues = ["pool.py: checkout"]
    s2.verification = [{"command": "pytest -k handshake", "expected": "passed"}]
    ctx["solutions"].add(s2)

    res = service.synthesize_solutions(problem.problem_id)
    assert res is not None

    canonical = service._solutions.get(problem.canonical_solution_id)
    assert canonical is not None
    assert canonical.root_cause_pattern == "ssl session reused across forked workers"
    assert set(canonical.localization_cues) == {
        "ssl_ctx.py: wrap_socket",
        "pool.py: checkout",
    }
    assert len(canonical.verification) == 2


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
    assert best.get("steps") == []


def test_format_full_includes_solution_steps() -> None:
    service, ctx = _build_service()
    problem = _make_problem("steps query match", ctx["author"].agent_id)
    ctx["problems"].add(problem)
    sol = _make_solution(
        problem.problem_id,
        ctx["author"].agent_id,
        "patch the handler",
        0.9,
    )
    sol.steps = ["Open file", "Apply fix"]
    ctx["solutions"].add(sol)

    payload = service.search_problems(query="steps query", limit=5, format="full")
    best = payload["results"][0]["best_solution"]
    assert best is not None
    assert best["steps"] == ["Open file", "Apply fix"]


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
