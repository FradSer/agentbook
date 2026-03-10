from __future__ import annotations

from uuid import UUID

import pytest

from app.application.service_v2 import AgentbookServiceV2
from app.domain.models import Problem
from app.infrastructure.persistence.in_memory_v2 import (
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemorySolutionRepository,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_ID: UUID = UUID("00000000-0000-0000-0000-000000000042")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _null_embedder(text: str) -> list[float]:
    """Embedder stub that returns a zero vector (no semantic similarity)."""
    return [0.0, 0.0, 0.0]


def _fixed_embedder(text: str) -> list[float]:
    """Embedder stub that always returns the same unit vector."""
    return [1.0, 0.0, 0.0]


def make_service(
    embedder=None,
) -> tuple[AgentbookServiceV2, InMemoryProblemRepository, InMemorySolutionRepository]:
    problems_repo = InMemoryProblemRepository()
    solutions_repo = InMemorySolutionRepository()
    outcomes_repo = InMemoryOutcomeRepository()
    service = AgentbookServiceV2(
        problems=problems_repo,
        solutions=solutions_repo,
        outcomes=outcomes_repo,
        embedder=embedder or _null_embedder,
    )
    return service, problems_repo, solutions_repo


# ---------------------------------------------------------------------------
# Test 1 — Problem-only contribution
# ---------------------------------------------------------------------------


def test_contribute_problem_only_creates_problem_no_solution() -> None:
    service, problems_repo, solutions_repo = make_service()

    result = service.contribute(
        author_id=AGENT_ID,
        description="This is a well-formed problem description about FastAPI",
    )

    assert result["status"] == "problem_created"
    assert result["problem_id"] is not None
    assert result["solution_id"] is None

    p = problems_repo.get(result["problem_id"])
    assert p is not None
    assert p.description == "This is a well-formed problem description about FastAPI"


# ---------------------------------------------------------------------------
# Test 2 — Problem + solution, author_verified=True
# ---------------------------------------------------------------------------


def test_contribute_with_solution_author_verified_sets_confidence_0_5() -> None:
    service, problems_repo, solutions_repo = make_service()

    result = service.contribute(
        author_id=AGENT_ID,
        description="Problem about configuring pgvector in PostgreSQL",
        solution_content="Run CREATE EXTENSION vector; then VACUUM ANALYZE your table to rebuild indexes",
        author_verified=True,
    )

    assert result["status"] == "knowledge_created"
    assert result["solution_id"] is not None

    sol = solutions_repo.get(result["solution_id"])
    assert sol is not None
    assert sol.confidence == 0.5
    assert sol.problem_id == result["problem_id"]


# ---------------------------------------------------------------------------
# Test 3 — Problem + solution, author_verified=False
# ---------------------------------------------------------------------------


def test_contribute_with_solution_unverified_sets_confidence_0_3() -> None:
    service, problems_repo, solutions_repo = make_service()

    result = service.contribute(
        author_id=AGENT_ID,
        description="Problem about handling Python import errors in 3.12",
        solution_content="Add __init__.py files to your package directories and check sys.path",
        author_verified=False,
    )

    assert result["solution_id"] is not None
    sol = solutions_repo.get(result["solution_id"])
    assert sol is not None
    assert sol.confidence == 0.3


# ---------------------------------------------------------------------------
# Test 4 — Quality gate rejection (description too short)
# ---------------------------------------------------------------------------


def test_contribute_short_description_raises_value_error_stores_nothing() -> None:
    service, problems_repo, solutions_repo = make_service()

    with pytest.raises(ValueError):
        service.contribute(author_id=AGENT_ID, description="too short")

    assert len(problems_repo.list_all()) == 0


# ---------------------------------------------------------------------------
# Test 5 — Duplicate detection (similar problem exists)
# ---------------------------------------------------------------------------


def test_contribute_similar_problem_exists_does_not_raise() -> None:
    service, problems_repo, solutions_repo = make_service(embedder=_fixed_embedder)

    # Pre-seed a problem with embedding [1.0, 0.0, 0.0]
    existing = Problem(
        author_id=AGENT_ID,
        description="Existing problem about FastAPI startup configuration",
        embedding=[1.0, 0.0, 0.0],
    )
    problems_repo.add(existing)

    # contribute() with the fixed embedder produces an identical embedding
    result = service.contribute(
        author_id=AGENT_ID,
        description="Another problem about FastAPI startup configuration details",
    )

    assert result["status"] in ("similar_exists", "knowledge_created", "problem_created")
    assert "problem_id" in result


# ---------------------------------------------------------------------------
# Test 6 — solution_count incremented on problem
# ---------------------------------------------------------------------------


def test_contribute_with_solution_increments_problem_solution_count() -> None:
    service, problems_repo, solutions_repo = make_service()

    result = service.contribute(
        author_id=AGENT_ID,
        description="Problem about Redis connection timeouts in production",
        solution_content="Increase the connection pool size by setting max_connections=50 in your Redis config",
        author_verified=True,
    )

    p = problems_repo.get(result["problem_id"])
    assert p is not None
    assert p.solution_count == 1
