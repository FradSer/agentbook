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

from backend.infrastructure.persistence.sqlalchemy_repositories import (
    SQLAlchemyProblemRepository,
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


def test_hybrid_search_skips_dense_when_probe_reports_unavailable(monkeypatch):
    repo = SQLAlchemyProblemRepository(lambda: _FakeSession())
    monkeypatch.setattr(repo, "retrieval_status", lambda: ("postgres", False))

    results, diagnostics = repo.find_hybrid_with_diagnostics(
        query_embedding=[0.1] * 1024,
        query_text="db pool",
        limit=5,
    )

    assert results == []
    assert diagnostics.pgvector_available is False
