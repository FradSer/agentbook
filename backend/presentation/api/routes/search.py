from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request

from backend.application.service import AgentbookService
from backend.core.rate_limit import limiter
from backend.domain.models import Agent
from backend.presentation.api.deps import get_optional_current_agent, get_service
from backend.presentation.api.schemas import (
    BestSolutionResponse,
    SearchResponse,
    SearchResultResponse,
)

router = APIRouter(prefix="/v1", tags=["search"])


@router.get("/search", response_model=SearchResponse)
@limiter.limit("30/minute")
def search_problems(
    request: Request,
    q: str = Query(min_length=1),
    error_log: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    service: AgentbookService = Depends(get_service),
    agent: Agent | None = Depends(get_optional_current_agent),
) -> SearchResponse:
    payload = service.search_problems(query=q, error_log=error_log, limit=limit)
    results = []
    for item in payload["results"]:
        best_sol = item.get("best_solution")
        results.append(
            SearchResultResponse(
                problem_id=item["problem_id"],
                description_preview=item["description"][:200],
                tags=item.get("tags") or [],
                similarity_score=item["similarity_score"],
                best_solution=None
                if best_sol is None
                else BestSolutionResponse(
                    solution_id=best_sol["solution_id"],
                    content_preview=best_sol["content_preview"],
                    confidence=best_sol["confidence"],
                ),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
        )
    return SearchResponse(results=results, total=payload["total"])
