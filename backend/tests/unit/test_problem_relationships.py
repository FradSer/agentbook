"""Unit tests for cross-problem knowledge graph.

Tests InMemoryProblemRelationshipRepository CRUD, _compute_relationships
relationship types, and get_cross_problem_solutions.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from backend.domain.models import Problem, ProblemRelationship, Solution
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRelationshipRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)

AUTHOR_ID = UUID("00000000-0000-0000-0000-000000000001")


def _make_problem(
    description: str = "test",
    embedding: list[float] | None = None,
    error_signature: str | None = None,
    tags: list[str] | None = None,
) -> Problem:
    return Problem(
        author_id=AUTHOR_ID,
        description=description,
        embedding=embedding,
        error_signature=error_signature,
        tags=tags,
        review_status="approved",
    )


def _make_solution(
    problem_id: UUID,
    content: str = "fix it",
    confidence: float = 0.5,
) -> Solution:
    return Solution(
        problem_id=problem_id,
        author_id=AUTHOR_ID,
        content=content,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# InMemoryProblemRelationshipRepository
# ---------------------------------------------------------------------------


class TestInMemoryProblemRelationshipRepo:
    def test_add_and_find(self) -> None:
        repo = InMemoryProblemRelationshipRepository()
        src = uuid4()
        tgt = uuid4()
        rel = ProblemRelationship(
            source_problem_id=src,
            target_problem_id=tgt,
            relationship_type="vector_similarity",
            score=0.8,
        )
        repo.add(rel)
        found = repo.find_related(src)
        assert len(found) == 1
        assert found[0].target_problem_id == tgt

    def test_find_respects_min_score(self) -> None:
        repo = InMemoryProblemRelationshipRepository()
        src = uuid4()
        repo.add(
            ProblemRelationship(
                source_problem_id=src,
                target_problem_id=uuid4(),
                relationship_type="tag_overlap",
                score=0.2,
            )
        )
        repo.add(
            ProblemRelationship(
                source_problem_id=src,
                target_problem_id=uuid4(),
                relationship_type="tag_overlap",
                score=0.6,
            )
        )
        assert len(repo.find_related(src, min_score=0.5)) == 1

    def test_find_filters_by_type(self) -> None:
        repo = InMemoryProblemRelationshipRepository()
        src = uuid4()
        repo.add(
            ProblemRelationship(
                source_problem_id=src,
                target_problem_id=uuid4(),
                relationship_type="vector_similarity",
                score=0.8,
            )
        )
        repo.add(
            ProblemRelationship(
                source_problem_id=src,
                target_problem_id=uuid4(),
                relationship_type="tag_overlap",
                score=0.5,
            )
        )
        found = repo.find_related(src, relationship_types=["tag_overlap"])
        assert len(found) == 1
        assert found[0].relationship_type == "tag_overlap"

    def test_find_respects_limit(self) -> None:
        repo = InMemoryProblemRelationshipRepository()
        src = uuid4()
        for _ in range(5):
            repo.add(
                ProblemRelationship(
                    source_problem_id=src,
                    target_problem_id=uuid4(),
                    relationship_type="vector_similarity",
                    score=0.9,
                )
            )
        assert len(repo.find_related(src, limit=3)) == 3

    def test_find_sorted_by_score_desc(self) -> None:
        repo = InMemoryProblemRelationshipRepository()
        src = uuid4()
        repo.add(
            ProblemRelationship(
                source_problem_id=src,
                target_problem_id=uuid4(),
                relationship_type="vector_similarity",
                score=0.5,
            )
        )
        repo.add(
            ProblemRelationship(
                source_problem_id=src,
                target_problem_id=uuid4(),
                relationship_type="vector_similarity",
                score=0.9,
            )
        )
        found = repo.find_related(src)
        assert found[0].score > found[1].score

    def test_delete_by_source(self) -> None:
        repo = InMemoryProblemRelationshipRepository()
        src = uuid4()
        other = uuid4()
        repo.add(
            ProblemRelationship(
                source_problem_id=src,
                target_problem_id=uuid4(),
                relationship_type="vector_similarity",
                score=0.8,
            )
        )
        repo.add(
            ProblemRelationship(
                source_problem_id=other,
                target_problem_id=uuid4(),
                relationship_type="vector_similarity",
                score=0.7,
            )
        )
        repo.delete_by_source(src)
        assert len(repo.find_related(src)) == 0
        assert len(repo.find_related(other)) == 1

    def test_find_for_unknown_source_returns_empty(self) -> None:
        repo = InMemoryProblemRelationshipRepository()
        assert repo.find_related(uuid4()) == []


# ---------------------------------------------------------------------------
# _compute_relationships
# ---------------------------------------------------------------------------


def _build_service(**overrides):
    from backend.application.service import AgentbookService

    defaults = dict(
        agents=InMemoryAgentRepository(),
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
        problem_relationships=InMemoryProblemRelationshipRepository(),
    )
    defaults.update(overrides)
    return AgentbookService(**defaults)


class TestComputeRelationships:
    def test_tag_overlap_creates_relationship(self) -> None:
        svc = _build_service()
        p1 = _make_problem(tags=["python", "import", "numpy"])
        p2 = _make_problem(tags=["python", "import", "pandas"])
        svc._problems.add(p1)
        svc._problems.add(p2)

        svc._compute_relationships(p1)

        rels = svc._problem_relationships.find_related(p1.problem_id)
        assert len(rels) == 1
        assert rels[0].relationship_type == "tag_overlap"
        assert rels[0].target_problem_id == p2.problem_id

    def test_error_signature_prefix_match(self) -> None:
        svc = _build_service()
        p1 = _make_problem(error_signature="ImportError: no module named numpy")
        p2 = _make_problem(error_signature="ImportError: no module named pandas")
        p3 = _make_problem(error_signature="TypeError: unsupported operand")
        svc._problems.add(p1)
        svc._problems.add(p2)
        svc._problems.add(p3)

        svc._compute_relationships(p1)

        rels = svc._problem_relationships.find_related(p1.problem_id)
        assert len(rels) == 1
        assert rels[0].target_problem_id == p2.problem_id
        assert rels[0].relationship_type == "error_signature"

    def test_recompute_clears_stale(self) -> None:
        svc = _build_service()
        p1 = _make_problem(tags=["python"])
        p2 = _make_problem(tags=["python"])
        svc._problems.add(p1)
        svc._problems.add(p2)

        svc._compute_relationships(p1)
        assert len(svc._problem_relationships.find_related(p1.problem_id)) == 1

        # Remove the tag overlap by clearing p2's tags.
        p2.tags = []
        svc._problems.update(p2)
        svc._compute_relationships(p1)
        assert len(svc._problem_relationships.find_related(p1.problem_id)) == 0

    def test_no_self_relationship(self) -> None:
        svc = _build_service()
        p1 = _make_problem(tags=["python", "error"])
        svc._problems.add(p1)

        svc._compute_relationships(p1)
        rels = svc._problem_relationships.find_related(p1.problem_id)
        assert len(rels) == 0

    def test_noop_when_repo_is_none(self) -> None:
        svc = _build_service(problem_relationships=None)
        p1 = _make_problem(tags=["python"])
        svc._problems.add(p1)
        # Should not raise.
        svc._compute_relationships(p1)


# ---------------------------------------------------------------------------
# get_cross_problem_solutions
# ---------------------------------------------------------------------------


class TestGetCrossProblemSolutions:
    def test_returns_solutions_from_related_problems(self) -> None:
        svc = _build_service()
        p1 = _make_problem(tags=["python", "import"])
        p2 = _make_problem(tags=["python", "import", "numpy"])
        svc._problems.add(p1)
        svc._problems.add(p2)

        sol = _make_solution(p2.problem_id, "pip install numpy", confidence=0.7)
        svc._solutions.add(sol)

        svc._compute_relationships(p1)

        results = svc.get_cross_problem_solutions(p1.problem_id)
        assert len(results) == 1
        assert results[0]["from_problem_id"] == str(p2.problem_id)
        assert results[0]["confidence"] == 0.7

    def test_skips_low_confidence_solutions(self) -> None:
        svc = _build_service()
        p1 = _make_problem(tags=["python", "error"])
        p2 = _make_problem(tags=["python", "error"])
        svc._problems.add(p1)
        svc._problems.add(p2)

        sol = _make_solution(p2.problem_id, "bad fix", confidence=0.1)
        svc._solutions.add(sol)

        svc._compute_relationships(p1)

        results = svc.get_cross_problem_solutions(p1.problem_id)
        assert len(results) == 0

    def test_respects_limit(self) -> None:
        svc = _build_service()
        p1 = _make_problem(tags=["a", "b", "c"])
        svc._problems.add(p1)

        for _ in range(5):
            px = _make_problem(tags=["a", "b", "c"])
            svc._problems.add(px)
            sol = _make_solution(px.problem_id, "fix", confidence=0.8)
            svc._solutions.add(sol)

        svc._compute_relationships(p1)
        results = svc.get_cross_problem_solutions(p1.problem_id, limit=2)
        assert len(results) <= 2

    def test_empty_when_no_relationships_repo(self) -> None:
        svc = _build_service(problem_relationships=None)
        assert svc.get_cross_problem_solutions(uuid4()) == []
