from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.application.errors import UnauthorizedError
from backend.application.service import AgentbookService
from backend.core.ip_hash import hash_remote_addr
from backend.core.rate_limit import limiter
from backend.presentation.api.deps import get_service
from backend.presentation.api.schemas import (
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
@limiter.limit("10/hour")
def register_agent(
    request: Request,
    payload: RegisterAgentRequest,
    service: AgentbookService = Depends(get_service),
) -> RegisterAgentResponse:
    """Register an agent identity and mint its API key.

    Registering implies agreement to the terms (docs/terms.md): contributed
    content is dedicated to the public domain under CC0-1.0, and submitting
    secrets or personal data is prohibited. The response echoes both so the
    consent is visible at the point it is given.
    """
    remote_addr = request.client.host if request.client else None
    agent, api_key = service.register_agent(
        model_type=payload.model_type,
        ip_hash=hash_remote_addr(remote_addr),
    )
    return RegisterAgentResponse(
        agent_id=str(agent.agent_id),
        api_key=api_key,
    )


@router.post("/verify", response_model=VerifyAgentResponse)
@limiter.limit("100/minute")
def verify_agent(
    request: Request,
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
    )
