"""Regression: hybrid search must degrade, not 500, on JSON-backed columns.

On Railway the pgvector extension is absent, so ``problems.embedding_v2`` is a
JSON-backed ``FlexibleVector`` with no ``cosine_distance``. Building that
``order_by`` raises ``AttributeError`` at statement-construction time (not a DB
error), which previously escaped ``find_hybrid_with_diagnostics`` and surfaced
as a 500 once Gemini embeddings started succeeding. The dense leg must be gated
on the real column type and the failure caught so the search falls back to the
lexical leg.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from backend.domain.models import Problem
from backend.infrastructure.persistence.sqlalchemy_models import ProblemORM
from backend.infrastructure.persistence.sqlalchemy_repositories import (
    SQLAlchemyProblemRepository,
    _cosine,
)


class _FakeResult:
    def scalars(self):
        return self

    def all(self):
        return []


class _FakeSession:
    def __init__(self):
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *args, **kwargs):
        return _FakeResult()


def test_hybrid_search_degrades_when_column_has_no_cosine_distance(monkeypatch):
    repo = SQLAlchemyProblemRepository(lambda: _FakeSession())
    # Probe claims dense is available so the dense leg is attempted; the real
    # FlexibleVector column then raises AttributeError on cosine_distance.
    monkeypatch.setattr(repo, "retrieval_status", lambda: ("postgres", True))

    results, diagnostics = repo.find_hybrid_with_diagnostics(
        query_embedding=[0.1] * 1024,
        query_text="database connection pool exhausted",
        limit=5,
    )

    assert results == []
    assert diagnostics.pgvector_available is False
    assert diagnostics.dense_hits == 0


def test_cosine_similarity_ranks_and_guards():
    assert _cosine([1.0, 0.0], [2.0, 0.0]) == 1.0
    assert _cosine([1.0, 0.0], [0.0, 5.0]) == 0.0
    assert _cosine([1.0, 0.0], [1.0]) == -1.0  # length mismatch
    assert _cosine([1.0, 0.0], None) == -1.0  # missing vector
    assert _cosine([0.0, 0.0], [1.0, 1.0]) == -1.0  # zero vector


def test_in_memory_dense_ranks_by_cosine_and_drops_unrelated():
    near = ProblemORM(
        problem_id=str(uuid4()),
        author_id=str(uuid4()),
        description="near",
        review_status="approved",
        embedding=[1.0, 0.0],
        embedding_v2=[1.0, 0.0],
    )
    far = ProblemORM(
        problem_id=str(uuid4()),
        author_id=str(uuid4()),
        description="orthogonal",
        review_status="approved",
        embedding=[0.0, 1.0],
        embedding_v2=[0.0, 1.0],
    )

    class _Result:
        def scalars(self):
            return self

        def all(self):
            return [far, near]

    class _Sess:
        def execute(self, *a, **k):
            return _Result()

    repo = SQLAlchemyProblemRepository(lambda: _Sess())
    ranked = repo._in_memory_dense(_Sess(), [1.0, 0.0], candidate_pool=5)

    # near has cosine 1.0; orthogonal scores 0.0 and is dropped (score > 0).
    assert [p.description for p in ranked] == ["near"]


def test_in_memory_dense_runs_when_pgvector_unavailable(monkeypatch):
    repo = SQLAlchemyProblemRepository(lambda: _FakeSession())
    monkeypatch.setattr(repo, "retrieval_status", lambda: ("postgres", False))
    p1 = Problem(author_id=uuid4(), description="db pool exhausted")
    p2 = Problem(author_id=uuid4(), description="docker build fail")
    monkeypatch.setattr(repo, "_in_memory_dense", lambda *a, **k: [p1, p2])

    results, diagnostics = repo.find_hybrid_with_diagnostics(
        query_embedding=[0.1] * 4,
        query_text="",
        limit=5,
    )

    assert diagnostics.dense_hits == 2
    assert diagnostics.pgvector_available is False
    assert {p.problem_id for p, _ in results} == {p1.problem_id, p2.problem_id}


def test_hybrid_search_skips_dense_when_probe_reports_unavailable(monkeypatch):
    # No query_embedding -> no dense leg at all (neither DB-side nor in-memory).
    repo = SQLAlchemyProblemRepository(lambda: _FakeSession())
    monkeypatch.setattr(repo, "retrieval_status", lambda: ("postgres", False))

    results, diagnostics = repo.find_hybrid_with_diagnostics(
        query_embedding=None,
        query_text="db pool",
        limit=5,
    )

    assert results == []
    assert diagnostics.pgvector_available is False
    assert diagnostics.dense_hits == 0
