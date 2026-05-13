"""Hybrid retrieval (dense + sparse + RRF) for `find_hybrid`."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.domain.models import Problem
from backend.domain.search import rrf_fuse
from backend.infrastructure.persistence.in_memory import InMemoryProblemRepository


def _make_problem(
    description: str,
    embedding: list[float] | None = None,
    review_status: str = "approved",
) -> Problem:
    return Problem(
        problem_id=uuid4(),
        author_id=uuid4(),
        description=description,
        embedding=embedding,
        created_at=datetime.now(UTC),
        last_activity_at=datetime.now(UTC),
        review_status=review_status,
    )


def test_rrf_fuse_orders_consensus_first() -> None:
    p1 = _make_problem("alpha")
    p2 = _make_problem("beta")
    p3 = _make_problem("gamma")
    fused = rrf_fuse([[p1, p2, p3], [p1, p3]], k=60, limit=10)
    assert fused[0][0].problem_id == p1.problem_id


def test_in_memory_find_hybrid_returns_lexical_match() -> None:
    repo = InMemoryProblemRepository()
    target = _make_problem("TypeError on json.dumps with Decimal")
    repo.add(target)
    repo.add(_make_problem("Random unrelated text about cats"))
    results = repo.find_hybrid(
        query_embedding=None,
        query_text="typeerror json.dumps",
        limit=5,
    )
    assert any(p.problem_id == target.problem_id for p, _ in results)


def test_in_memory_find_hybrid_returns_semantic_match() -> None:
    repo = InMemoryProblemRepository()
    target_embedding = [1.0, 0.0, 0.0]
    target = _make_problem("asyncio event loop crashes", embedding=target_embedding)
    other = _make_problem("nothing in common", embedding=[0.0, 1.0, 0.0])
    repo.add(target)
    repo.add(other)

    results = repo.find_hybrid(
        query_embedding=[0.99, 0.01, 0.0],
        query_text="completely different tokens",
        limit=5,
    )
    assert results, "expected dense match to surface despite zero token overlap"
    assert results[0][0].problem_id == target.problem_id


def test_in_memory_find_hybrid_excludes_unapproved() -> None:
    repo = InMemoryProblemRepository()
    pending = _make_problem(
        "TypeError pending review",
        embedding=[1.0, 0.0],
        review_status="pending",
    )
    repo.add(pending)
    results = repo.find_hybrid(
        query_embedding=[1.0, 0.0],
        query_text="typeerror pending review",
        limit=5,
    )
    assert results == []


def test_in_memory_find_hybrid_dual_leg_outranks_single_leg() -> None:
    repo = InMemoryProblemRepository()
    dual = _make_problem("redis connection timeout pooling", embedding=[1.0, 0.0])
    dense_only = _make_problem("xyz qrs", embedding=[0.99, 0.05])
    repo.add(dual)
    repo.add(dense_only)

    results = repo.find_hybrid(
        query_embedding=[1.0, 0.0],
        query_text="redis connection timeout",
        limit=5,
    )
    assert results[0][0].problem_id == dual.problem_id


def test_service_search_uses_hybrid_when_available() -> None:
    """Smoke-test: AgentbookService wires `find_hybrid` and returns approved rows."""
    from backend.application.service import AgentbookService
    from backend.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
    )

    problems = InMemoryProblemRepository()
    target = _make_problem("Cannot connect to PostgreSQL on Railway", embedding=None)
    problems.add(target)

    service = AgentbookService(
        agents=InMemoryAgentRepository(),
        problems=problems,
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )

    payload = service.search_problems(query="postgresql railway", limit=5)
    ids = [r["problem_id"] for r in payload["results"]]
    assert str(target.problem_id) in ids
