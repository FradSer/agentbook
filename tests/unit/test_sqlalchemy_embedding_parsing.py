from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.infrastructure.persistence.sqlalchemy_repositories import _to_thread_domain


def _build_thread_row(embedding: object) -> SimpleNamespace:
    return SimpleNamespace(
        thread_id=str(uuid4()),
        author_id=str(uuid4()),
        title="title",
        body="body",
        tags=["python"],
        error_log=None,
        environment_context=None,
        embedding=embedding,
        created_at=datetime.now(timezone.utc),
        reviewed_at=None,
        review_status=None,
        review_score=None,
    )


def test_to_thread_domain_parses_pgvector_string_embedding() -> None:
    row = _build_thread_row("[0.1, 0.2, 0.3]")

    thread = _to_thread_domain(row)

    assert thread.embedding == [0.1, 0.2, 0.3]


def test_to_thread_domain_keeps_sequence_embedding() -> None:
    row = _build_thread_row([0.1, 0.2, 0.3])

    thread = _to_thread_domain(row)

    assert thread.embedding == [0.1, 0.2, 0.3]
