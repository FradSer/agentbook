from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status

from backend.application.errors import UnauthorizedError
from backend.application.service import AgentbookService
from backend.core.auth import parse_bearer_token
from backend.domain.models import Agent


def get_service(request: Request) -> AgentbookService:
    return request.app.state.service


def get_current_agent(
    service: AgentbookService = Depends(get_service),
    authorization: str | None = Header(default=None),
    x_agent_info: str | None = Header(default=None, alias="X-Agent-Info"),
) -> Agent:
    parsed = parse_bearer_token(authorization, required_prefix="ak_")
    if not parsed.ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=parsed.detail,
        )

    try:
        return service.authenticate(api_key=parsed.token, agent_info=x_agent_info)
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
    parsed = parse_bearer_token(authorization, required_prefix="ak_")
    if not parsed.ok:
        request.state.agent = None
        return None

    try:
        agent = service.authenticate(api_key=parsed.token, agent_info=x_agent_info)
    except UnauthorizedError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error
    request.state.agent = agent
    return agent
