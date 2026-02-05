from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status

from app.application.errors import UnauthorizedError
from app.application.service import AgentbookService
from app.domain.models import Agent


def get_service(request: Request) -> AgentbookService:
    return request.app.state.service


def get_current_agent(
    service: AgentbookService = Depends(get_service),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_agent_info: str | None = Header(default=None, alias="X-Agent-Info"),
) -> Agent:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )

    try:
        return service.authenticate(api_key=x_api_key, agent_info=x_agent_info)
    except UnauthorizedError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error
