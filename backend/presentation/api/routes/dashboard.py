from __future__ import annotations

from fastapi import APIRouter, Depends
from uuid import UUID

from backend.application.errors import NotFoundError
from backend.application.service import AgentbookService
from backend.presentation.api.deps import get_service

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


@router.get("/radar")
def get_radar(service: AgentbookService = Depends(get_service)) -> dict:
    return service.get_radar()


@router.get("/metrics")
def get_metrics(service: AgentbookService = Depends(get_service)) -> dict:
    return service.get_metrics()


@router.get("/research")
def get_research_history(
    problem_id: UUID,
    service: AgentbookService = Depends(get_service),
) -> dict:
    history = service.get_research_history(problem_id)
    return {"history": history}


@router.get("/research/candidates")
def get_research_candidates(
    limit: int = 10,
    service: AgentbookService = Depends(get_service),
) -> dict:
    candidates = service.find_research_candidates(limit=limit)
    return {"candidates": candidates}


@router.get("/solutions/{solution_id}/lineage")
def get_solution_lineage(
    solution_id: UUID,
    service: AgentbookService = Depends(get_service),
) -> dict:
    try:
        lineage = service.get_solution_lineage(solution_id)
        return {"lineage": lineage}
    except NotFoundError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(exc))

