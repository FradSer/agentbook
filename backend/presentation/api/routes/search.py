from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from backend.application.service import AgentbookService
from backend.core.rate_limit import dynamic_search_limit, limiter
from backend.domain.models import Agent
from backend.presentation.api.deps import get_optional_current_agent, get_service
from backend.presentation.api.schemas import (
    BestSolutionResponse,
    SearchResponse,
    SearchResultResponse,
)

router = APIRouter(prefix="/v1", tags=["search"])

_VALID_INCLUDE = {"solutions", "outcomes", "lineage"}


def _parse_include(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    parts = {token.strip() for token in raw.split(",") if token.strip()}
    return {p for p in parts if p in _VALID_INCLUDE} or None


@router.get("/search", response_model=SearchResponse)
@limiter.limit(dynamic_search_limit)
def search_problems(
    request: Request,
    q: str = Query(min_length=1),
    error_log: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    include: str | None = Query(default=None),
    format: Literal["concise", "full"] = Query(default="concise"),
    service: AgentbookService = Depends(get_service),
    agent: Agent | None = Depends(get_optional_current_agent),
) -> SearchResponse:
    include_set = _parse_include(include)
    payload = service.search_problems(
        query=q,
        error_log=error_log,
        limit=limit,
        include=include_set,
        format=format,
    )
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
                solutions=item.get("solutions"),
                outcomes=item.get("outcomes"),
                lineage=item.get("lineage"),
            )
        )
    return SearchResponse(results=results, total=payload["total"])
