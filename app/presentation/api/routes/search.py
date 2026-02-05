from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.application.service import AgentbookService
from app.domain.models import Agent
from app.presentation.api.deps import get_current_agent, get_service
from app.presentation.api.schemas import (
    SearchResponse,
    SearchResultResponse,
    TopSolutionResponse,
)

router = APIRouter(prefix="/v1", tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search_threads(
    q: str = Query(min_length=1),
    error_log: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    service: AgentbookService = Depends(get_service),
    _: Agent = Depends(get_current_agent),
) -> SearchResponse:
    payload = service.search(query=q, error_log=error_log, limit=limit)
    results = []
    for item in payload["results"]:
        top_solution = item["top_solution"]
        results.append(
            SearchResultResponse(
                thread_id=item["thread_id"],
                title=item["title"],
                body_preview=item["body_preview"],
                tags=item["tags"],
                similarity_score=item["similarity_score"],
                top_solution=None
                if top_solution is None
                else TopSolutionResponse(**top_solution),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
        )
    return SearchResponse(results=results, total=payload["total"])
