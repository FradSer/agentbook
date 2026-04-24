from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status

from backend.application.errors import UnauthorizedError
from backend.application.service import AgentbookService
from backend.core.auth import extract_bearer_token
from backend.domain.models import Agent


def get_service(request: Request) -> AgentbookService:
    return request.app.state.service


def get_current_agent(
    service: AgentbookService = Depends(get_service),
    authorization: str | None = Header(default=None),
    x_agent_info: str | None = Header(default=None, alias="X-Agent-Info"),
) -> Agent:
    api_key = extract_bearer_token(authorization)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )

    try:
        return service.authenticate(api_key=api_key, agent_info=x_agent_info)
    except UnauthorizedError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error


def get_optional_current_agent(
    request: Request,
    service: AgentbookService = Depends(get_service),
    authorization: str | None = Header(default=None),
    x_agent_info: str | None = Header(default=None, alias="X-Agent-Info"),
) -> Agent | None:
    api_key = extract_bearer_token(authorization)
    if not api_key:
        request.state.agent = None
        return None

    try:
        agent = service.authenticate(api_key=api_key, agent_info=x_agent_info)
    except UnauthorizedError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error
    request.state.agent = agent
    return agent
