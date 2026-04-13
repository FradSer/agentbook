from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status

from backend.application.errors import UnauthorizedError
from backend.application.service import AgentbookService
from backend.domain.models import Agent


def get_service(request: Request) -> AgentbookService:
    return request.app.state.service


def _extract_bearer_token(authorization: str | None) -> str | None:
    """Extract Bearer token from Authorization header.

    Args:
        authorization: Authorization header value

    Returns:
        API key if valid Bearer token, None otherwise
    """
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        return None
    return authorization[7:].strip()


def get_current_agent(
    service: AgentbookService = Depends(get_service),
    authorization: str | None = Header(default=None),
    x_agent_info: str | None = Header(default=None, alias="X-Agent-Info"),
) -> Agent:
    api_key = _extract_bearer_token(authorization)
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
    api_key = _extract_bearer_token(authorization)
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
