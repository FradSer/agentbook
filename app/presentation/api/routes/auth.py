from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.errors import UnauthorizedError
from app.application.service import AgentbookService
from app.presentation.api.deps import get_service
from app.presentation.api.schemas import (
    RegisterAgentRequest,
    RegisterAgentResponse,
    VerifyAgentRequest,
    VerifyAgentResponse,
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


@router.post("/verify", response_model=VerifyAgentResponse)
def verify_agent(
    payload: VerifyAgentRequest,
    service: AgentbookService = Depends(get_service),
) -> VerifyAgentResponse:
    try:
        agent = service.authenticate(api_key=payload.api_key)
    except UnauthorizedError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)
        ) from error
    return VerifyAgentResponse(
        agent_id=str(agent.agent_id),
        model_type=agent.model_type,
        token_balance=agent.token_balance,
    )
