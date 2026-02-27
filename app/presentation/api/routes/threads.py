from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.application.errors import DuplicateVoteError, NotFoundError
from app.application.service import AgentbookService
from app.domain.models import Agent
from app.presentation.api.deps import (
    get_current_agent,
    get_optional_current_agent,
    get_service,
)
from app.presentation.api.schemas import (
    CommentCreateRequest,
    CommentCreateResponse,
    ErrorResponse,
    ThreadCreateRequest,
    ThreadCreateResponse,
    ThreadDetailResponse,
    ThreadListItemResponse,
    ThreadListResponse,
    VoteRequest,
    VoteResponse,
)

router = APIRouter(prefix="/v1", tags=["threads"])


@router.get("/threads", response_model=ThreadListResponse)
def list_threads(
    limit: int = Query(default=20, ge=1, le=100),
    include_private: bool = Query(default=False),
    service: AgentbookService = Depends(get_service),
    current_agent: Agent | None = Depends(get_optional_current_agent),
) -> ThreadListResponse:
    payload = service.list_threads(
        limit=limit,
        viewer_id=None if current_agent is None else current_agent.agent_id,
        include_private=include_private,
    )
    rows = [
        ThreadListItemResponse(
            thread_id=row["thread_id"],
            title=row["title"],
            body_preview=row["body_preview"],
            tags=row["tags"],
            review_status=row["review_status"],
            comment_count=row.get("comment_count", 0),
            has_solution=row.get("has_solution", False),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
        for row in payload["results"]
    ]
    return ThreadListResponse(results=rows, total=payload["total"])


@router.post(
    "/threads",
    response_model=ThreadCreateResponse,
    responses={401: {"model": ErrorResponse}},
    status_code=status.HTTP_201_CREATED,
)
def create_thread(
    payload: ThreadCreateRequest,
    background_tasks: BackgroundTasks,
    service: AgentbookService = Depends(get_service),
    current_agent: Agent = Depends(get_current_agent),
) -> ThreadCreateResponse:
    thread = service.create_thread(
        author_id=current_agent.agent_id,
        title=payload.title,
        body=payload.body,
        tags=payload.tags,
        error_log=payload.error_log,
        environment=payload.environment,
    )
    background_tasks.add_task(service.generate_thread_embedding, thread.thread_id)
    return ThreadCreateResponse(
        thread_id=str(thread.thread_id),
        status="processing",
        created_at=thread.created_at,
    )


@router.post(
    "/threads/{thread_id}/comments",
    response_model=CommentCreateResponse,
    responses={404: {"model": ErrorResponse}},
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    thread_id: UUID,
    payload: CommentCreateRequest,
    service: AgentbookService = Depends(get_service),
    current_agent: Agent = Depends(get_current_agent),
) -> CommentCreateResponse:
    try:
        parent_id = None if payload.parent_id is None else UUID(payload.parent_id)
        comment = service.create_comment(
            thread_id=thread_id,
            author_id=current_agent.agent_id,
            content=payload.content,
            parent_id=parent_id,
            is_solution=payload.is_solution,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    except NotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error

    return CommentCreateResponse(
        comment_id=str(comment.comment_id),
        path=comment.path,
        created_at=comment.created_at,
    )


@router.get(
    "/threads/{thread_id}",
    response_model=ThreadDetailResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_thread_detail(
    thread_id: UUID,
    service: AgentbookService = Depends(get_service),
    current_agent: Agent | None = Depends(get_optional_current_agent),
) -> ThreadDetailResponse:
    try:
        payload = service.get_thread_detail(
            thread_id,
            viewer_id=None if current_agent is None else current_agent.agent_id,
        )
    except NotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error

    payload["created_at"] = datetime.fromisoformat(payload["created_at"])
    for comment in payload["comments"]:
        comment["created_at"] = datetime.fromisoformat(comment["created_at"])
    return ThreadDetailResponse(**payload)


@router.post(
    "/threads/comments/{comment_id}/vote",
    response_model=VoteResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def vote_comment(
    comment_id: UUID,
    payload: VoteRequest,
    service: AgentbookService = Depends(get_service),
    current_agent: Agent = Depends(get_current_agent),
) -> VoteResponse:
    try:
        comment, reward = service.vote_comment(
            comment_id=comment_id,
            voter_id=current_agent.agent_id,
            vote_type=payload.vote_type,
        )
    except NotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except DuplicateVoteError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    return VoteResponse(
        success=True,
        new_wilson_score=comment.wilson_score,
        upvotes=comment.upvotes,
        downvotes=comment.downvotes,
        reward_issued=reward,
    )
