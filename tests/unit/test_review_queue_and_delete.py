from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.application.errors import NotFoundError
from app.application.service import AgentbookService
from app.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryCommentRepository,
    InMemoryThreadRepository,
    InMemoryTokenTransactionRepository,
    InMemoryVoteRepository,
)


def create_service() -> tuple[AgentbookService, InMemoryThreadRepository, InMemoryCommentRepository]:
    threads = InMemoryThreadRepository()
    comments = InMemoryCommentRepository()
    service = AgentbookService(
        agents=InMemoryAgentRepository(),
        threads=threads,
        comments=comments,
        votes=InMemoryVoteRepository(),
        transactions=InMemoryTokenTransactionRepository(),
        embedding_provider=None,
    )
    return service, threads, comments


def test_delete_thread_removes_thread() -> None:
    service, _threads, _comments = create_service()
    author, _ = service.register_agent(model_type="claude")
    thread = service.create_thread(
        author_id=author.agent_id,
        title="delete me",
        body="body to delete",
        tags=[],
        error_log=None,
        environment=None,
    )

    service.delete_thread(thread.thread_id)

    assert service.get_thread(thread.thread_id) is None
    try:
        service.get_thread_detail(thread.thread_id, viewer_id=author.agent_id)
        raise AssertionError("expected NotFoundError")
    except NotFoundError:
        pass


def test_delete_comment_removes_comment() -> None:
    service, _threads, comments = create_service()
    author, _ = service.register_agent(model_type="claude")
    thread = service.create_thread(
        author_id=author.agent_id,
        title="thread",
        body="thread body",
        tags=[],
        error_log=None,
        environment=None,
    )
    comment = service.create_comment(
        thread_id=thread.thread_id,
        author_id=author.agent_id,
        content="comment body",
        parent_id=None,
        is_solution=False,
    )

    service.delete_comment(comment.comment_id)

    assert comments.get(comment.comment_id) is None


def test_get_unreviewed_threads_includes_retryable_error_items() -> None:
    service, _threads, _comments = create_service()
    author, _ = service.register_agent(model_type="claude")
    now = datetime.now(timezone.utc)

    pending = service.create_thread(
        author_id=author.agent_id,
        title="pending",
        body="pending body",
        tags=[],
        error_log=None,
        environment=None,
    )
    old_error = service.create_thread(
        author_id=author.agent_id,
        title="old error",
        body="old error body",
        tags=[],
        error_log=None,
        environment=None,
    )
    fresh_error = service.create_thread(
        author_id=author.agent_id,
        title="fresh error",
        body="fresh error body",
        tags=[],
        error_log=None,
        environment=None,
    )
    approved = service.create_thread(
        author_id=author.agent_id,
        title="approved",
        body="approved body",
        tags=[],
        error_log=None,
        environment=None,
    )

    service.update_thread_review(
        thread_id=old_error.thread_id,
        status="error",
        score=0.0,
        reviewed_at=now - timedelta(minutes=40),
    )
    service.update_thread_review(
        thread_id=fresh_error.thread_id,
        status="error",
        score=0.0,
        reviewed_at=now - timedelta(minutes=5),
    )
    service.update_thread_review(
        thread_id=approved.thread_id,
        status="approved",
        score=9.0,
        reviewed_at=now - timedelta(minutes=40),
    )

    rows = service.get_unreviewed_threads(
        limit=10,
        retry_error_before=now - timedelta(minutes=30),
    )
    ids = {thread.thread_id for thread in rows}

    assert pending.thread_id in ids
    assert old_error.thread_id in ids
    assert fresh_error.thread_id not in ids
    assert approved.thread_id not in ids


def test_get_unreviewed_comments_includes_retryable_error_items() -> None:
    service, _threads, _comments = create_service()
    author, _ = service.register_agent(model_type="claude")
    now = datetime.now(timezone.utc)
    thread = service.create_thread(
        author_id=author.agent_id,
        title="thread",
        body="thread body",
        tags=[],
        error_log=None,
        environment=None,
    )

    pending = service.create_comment(
        thread_id=thread.thread_id,
        author_id=author.agent_id,
        content="pending comment",
        parent_id=None,
        is_solution=False,
    )
    old_error = service.create_comment(
        thread_id=thread.thread_id,
        author_id=author.agent_id,
        content="old error comment",
        parent_id=None,
        is_solution=False,
    )
    fresh_error = service.create_comment(
        thread_id=thread.thread_id,
        author_id=author.agent_id,
        content="fresh error comment",
        parent_id=None,
        is_solution=False,
    )
    approved = service.create_comment(
        thread_id=thread.thread_id,
        author_id=author.agent_id,
        content="approved comment",
        parent_id=None,
        is_solution=False,
    )

    service.update_comment_review(
        comment_id=old_error.comment_id,
        status="error",
        score=0.0,
        reviewed_at=now - timedelta(minutes=40),
    )
    service.update_comment_review(
        comment_id=fresh_error.comment_id,
        status="error",
        score=0.0,
        reviewed_at=now - timedelta(minutes=5),
    )
    service.update_comment_review(
        comment_id=approved.comment_id,
        status="approved",
        score=9.0,
        reviewed_at=now - timedelta(minutes=40),
    )

    rows = service.get_unreviewed_comments(
        limit=10,
        retry_error_before=now - timedelta(minutes=30),
    )
    ids = {comment.comment_id for comment in rows}

    assert pending.comment_id in ids
    assert old_error.comment_id in ids
    assert fresh_error.comment_id not in ids
    assert approved.comment_id not in ids
