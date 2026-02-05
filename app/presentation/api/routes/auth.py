from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.application.service import AgentbookService
from app.presentation.api.deps import get_service
from app.presentation.api.schemas import (
    RegisterAgentRequest,
    RegisterAgentResponse,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterAgentResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_agent(
    payload: RegisterAgentRequest,
    service: AgentbookService = Depends(get_service),
) -> RegisterAgentResponse:
    agent, api_key = service.register_agent(model_type=payload.model_type)
    return RegisterAgentResponse(
        agent_id=str(agent.agent_id),
        api_key=api_key,
        token_balance=agent.token_balance,
    )
