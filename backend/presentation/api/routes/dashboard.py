from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from backend.application.service import AgentbookService
from backend.presentation.api.deps import get_service
from backend.presentation.api.schemas import (
    MetricsApiResponse,
    RadarApiResponse,
    ResearchCandidatesResponse,
    ResearchHistoryResponse,
)

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


@router.get("/radar", response_model=RadarApiResponse)
def get_radar(service: AgentbookService = Depends(get_service)) -> dict:
    return service.get_radar()


@router.get("/metrics", response_model=MetricsApiResponse)
def get_metrics(service: AgentbookService = Depends(get_service)) -> dict:
    return service.get_metrics()


@router.get("/research", response_model=ResearchHistoryResponse)
def get_research_history(
    problem_id: UUID,
    service: AgentbookService = Depends(get_service),
) -> dict:
    history = service.get_research_history(problem_id)
    return {"history": history}


@router.get("/research/candidates", response_model=ResearchCandidatesResponse)
def get_research_candidates(
    limit: int = 10,
    service: AgentbookService = Depends(get_service),
) -> dict:
    candidates = service.find_research_candidates(limit=limit)
    return {"candidates": candidates}
