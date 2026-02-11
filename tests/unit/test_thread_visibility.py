from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.errors import NotFoundError
from app.application.service import AgentbookService
from app.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryCommentRepository,
    InMemoryThreadRepository,
    InMemoryTokenTransactionRepository,
    InMemoryVoteRepository,
)


def create_service() -> AgentbookService:
    return AgentbookService(
        agents=InMemoryAgentRepository(),
        threads=InMemoryThreadRepository(),
        comments=InMemoryCommentRepository(),
        votes=InMemoryVoteRepository(),
        transactions=InMemoryTokenTransactionRepository(),
        embedding_provider=None,
    )


def test_list_threads_anonymous_only_sees_approved() -> None:
    service = create_service()
    author, _ = service.register_agent(model_type="claude")

    approved = service.create_thread(
        author_id=author.agent_id,
        title="approved",
        body="approved body",
        tags=[],
        error_log=None,
        environment=None,
    )
    pending = service.create_thread(
        author_id=author.agent_id,
        title="pending",
        body="pending body",
        tags=[],
        error_log=None,
        environment=None,
    )
    service.update_thread_review(
        thread_id=approved.thread_id,
        status="approved",
        score=8.0,
        reviewed_at=datetime.now(UTC),
    )

    payload = service.list_threads(limit=20, viewer_id=None, include_private=False)

    assert payload["total"] == 1
    assert payload["results"][0]["thread_id"] == str(approved.thread_id)
    assert payload["results"][0]["thread_id"] != str(pending.thread_id)
    assert payload["results"][0]["review_status"] == "approved"


def test_list_threads_include_private_for_owner_includes_pending_and_rejected() -> None:
    service = create_service()
    author, _ = service.register_agent(model_type="claude")
    other, _ = service.register_agent(model_type="gemini")

    approved = service.create_thread(
        author_id=other.agent_id,
        title="approved",
        body="approved body",
        tags=[],
        error_log=None,
        environment=None,
    )
    own_pending = service.create_thread(
        author_id=author.agent_id,
        title="own pending",
        body="body",
        tags=[],
        error_log=None,
        environment=None,
    )
    own_rejected = service.create_thread(
        author_id=author.agent_id,
        title="own rejected",
        body="body",
        tags=[],
        error_log=None,
        environment=None,
    )
    other_pending = service.create_thread(
        author_id=other.agent_id,
        title="other pending",
        body="body",
        tags=[],
        error_log=None,
        environment=None,
    )
    service.update_thread_review(
        thread_id=approved.thread_id,
        status="approved",
        score=8.0,
        reviewed_at=datetime.now(UTC),
    )
    service.update_thread_review(
        thread_id=own_rejected.thread_id,
        status="rejected",
        score=1.0,
        reviewed_at=datetime.now(UTC),
    )

    payload = service.list_threads(
        limit=20,
        viewer_id=author.agent_id,
        include_private=True,
    )
    ids = {row["thread_id"] for row in payload["results"]}
    status_by_id = {
        row["thread_id"]: row["review_status"] for row in payload["results"]
    }

    assert str(approved.thread_id) in ids
    assert str(own_pending.thread_id) in ids
    assert str(own_rejected.thread_id) in ids
    assert str(other_pending.thread_id) not in ids
    assert status_by_id[str(own_pending.thread_id)] == "pending"
    assert status_by_id[str(own_rejected.thread_id)] == "rejected"


def test_get_thread_detail_anonymous_cannot_access_private_thread() -> None:
    service = create_service()
    author, _ = service.register_agent(model_type="claude")
    thread = service.create_thread(
        author_id=author.agent_id,
        title="private",
        body="private body",
        tags=[],
        error_log=None,
        environment=None,
    )

    with pytest.raises(NotFoundError):
        service.get_thread_detail(thread.thread_id, viewer_id=None)


def test_get_thread_detail_owner_receives_pending_status_for_unreviewed_thread() -> (
    None
):
    service = create_service()
    author, _ = service.register_agent(model_type="claude")
    thread = service.create_thread(
        author_id=author.agent_id,
        title="pending",
        body="pending body",
        tags=[],
        error_log=None,
        environment=None,
    )

    payload = service.get_thread_detail(thread.thread_id, viewer_id=author.agent_id)

    assert payload["thread_id"] == str(thread.thread_id)
    assert payload["review_status"] == "pending"
