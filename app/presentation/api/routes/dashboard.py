from __future__ import annotations

from fastapi import APIRouter, Depends

from app.application.service_v2 import AgentbookServiceV2
from app.presentation.api.deps import get_service_v2

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


@router.get("/radar")
def get_radar(service: AgentbookServiceV2 = Depends(get_service_v2)) -> dict:
    return service.get_radar()


@router.get("/metrics")
def get_metrics(service: AgentbookServiceV2 = Depends(get_service_v2)) -> dict:
    return service.get_metrics()
