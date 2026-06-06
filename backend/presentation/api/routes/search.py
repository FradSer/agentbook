from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi.util import get_remote_address

from backend.application.service import AgentbookService, CallerContext
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
    pattern_class: str | None = Query(default=None),
    service: AgentbookService = Depends(get_service),
    agent: Agent | None = Depends(get_optional_current_agent),
) -> SearchResponse:
    query = q.strip()
    if not query:
        raise HTTPException(
            status_code=422,
            detail="Query must contain at least one non-whitespace character",
        )
    include_set = _parse_include(include)
    # Dedup-capable identity for the recurrence-density instrument, matching the
    # MCP recall path. Recorded best-effort and side-channel — response unchanged.
    caller = CallerContext.from_agent_or_remote(agent, get_remote_address(request))
    payload = service.search_problems(
        query=query,
        error_log=error_log,
        limit=limit,
        include=include_set,
        format=format,
        pattern_class=pattern_class.strip() if pattern_class else None,
        caller=caller,
    )
    results = []
    for item in payload["results"]:
        best_sol = item.get("best_solution")
        results.append(
            SearchResultResponse(
                problem_id=item["problem_id"],
                description_preview=item["description"][:200],
                tags=item.get("tags") or [],
                solution_count=item.get("solution_count", 0),
                best_confidence=item.get("best_confidence", 0.0),
                similarity_score=item["similarity_score"],
                match_quality=item.get("match_quality", "partial"),
                match_reasons=item.get("match_reasons", []),
                best_solution=None
                if best_sol is None
                else BestSolutionResponse(
                    solution_id=best_sol["solution_id"],
                    confidence=best_sol["confidence"],
                    content=best_sol["content"],
                    content_preview=best_sol["content_preview"],
                    content_truncated=best_sol.get("content_truncated", False),
                    steps=best_sol.get("steps") or [],
                    root_cause_pattern=best_sol.get("root_cause_pattern"),
                    localization_cues=best_sol.get("localization_cues") or [],
                    verification=best_sol.get("verification") or [],
                    root_cause_class=best_sol.get("root_cause_class"),
                    outcome_count=best_sol.get("outcome_count", 0),
                    confidence_inputs=best_sol.get("confidence_inputs"),
                ),
                created_at=datetime.fromisoformat(item["created_at"]),
                solutions=item.get("solutions"),
                outcomes=item.get("outcomes"),
                lineage=item.get("lineage"),
            )
        )
    return SearchResponse(
        results=results,
        total=payload["total"],
        no_good_match=payload.get("no_good_match", False),
        search_mode=payload.get("search_mode"),
        embedding_provider=payload.get("embedding_provider"),
        rerank_provider=payload.get("rerank_provider"),
    )
