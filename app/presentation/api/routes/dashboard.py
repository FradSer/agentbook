from __future__ import annotations

from fastapi import APIRouter, Depends

from app.application.service import AgentbookService
from app.presentation.api.deps import get_service

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


@router.get("/radar")
def get_radar(service: AgentbookService = Depends(get_service)) -> dict:
    return service.get_radar()


@router.get("/metrics")
def get_metrics(service: AgentbookService = Depends(get_service)) -> dict:
    return service.get_metrics()
