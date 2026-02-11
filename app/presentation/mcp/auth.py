"""Authentication middleware for MCP (Model Context Protocol) endpoints.

Provides token verification and agent injection into MCP context.
Follows Clean Architecture: delegates verification to AgentbookService.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.application.errors import UnauthorizedError
from app.application.service import AgentbookService
from app.domain.models import Agent


@dataclass(frozen=True, slots=True)
class TokenVerifier:
    """Verifies authentication tokens for MCP endpoints.

    Supports both Bearer tokens and X-API-Key headers for compatibility
    with existing Agentbook API clients and MCP-compliant agents.
    """

    service: AgentbookService
    api_key_prefix: str = "ak_"

    def verify(
        self,
        authorization: str | None = None,
        x_api_key: str | None = None,
    ) -> Agent:
        """Verify authentication token and return authenticated agent.

        Args:
            authorization: Bearer token from Authorization header
            x_api_key: API key from X-API-Key header

        Returns:
            Authenticated agent

        Raises:
            HTTPException: If authentication fails (401)
        """
        api_key = None

        if authorization:
            api_key = self._extract_bearer_token(authorization)
        elif x_api_key:
            api_key = x_api_key

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: provide Bearer token or X-API-Key header",
            )

        try:
            return self.service.authenticate(api_key=api_key, agent_info=None)
        except UnauthorizedError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(error),
            ) from error

    def _extract_bearer_token(self, authorization: str) -> str | None:
        """Extract API key from Bearer token.

        Args:
            authorization: Authorization header value

        Returns:
            API key if valid Bearer token, None otherwise
        """
        if not authorization.startswith("Bearer "):
            return None

        token = authorization[7:].strip()

        if not token.startswith(self.api_key_prefix):
            return None

        return token


def get_verifier(request: Request) -> TokenVerifier:
    """Get TokenVerifier instance from FastAPI app state.

    Args:
        request: FastAPI request

    Returns:
        TokenVerifier instance configured with AgentbookService
    """
    service = request.app.state.service
    return TokenVerifier(service=service)


class MCPAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to inject authenticated agent into request state for MCP endpoints.

    This middleware extracts authentication from headers and stores the
    authenticated agent in request.state.mcp_agent for use by MCP tools.
    """

    def __init__(self, app, api_key_prefix: str = "ak_"):
        super().__init__(app)
        self._api_key_prefix = api_key_prefix

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Any],
    ) -> Any:
        """Process request and inject agent into state if authenticated.

        For MCP endpoints, the authentication happens at the tool level
        via context. This middleware stores the verifier in app state.

        Args:
            request: FastAPI request
            call_next: Next middleware/handler

        Returns:
            Response from next middleware/handler
        """
        service = request.app.state.service
        verifier = TokenVerifier(service=service, api_key_prefix=self._api_key_prefix)

        authorization = request.headers.get("Authorization")
        x_api_key = request.headers.get("X-API-Key")

        try:
            if authorization or x_api_key:
                agent = verifier.verify(
                    authorization=authorization, x_api_key=x_api_key
                )
                request.state.mcp_agent = agent
        except HTTPException:
            pass

        return await call_next(request)


def get_current_mcp_agent(request: Request) -> Agent | None:
    """Get authenticated agent from request state for MCP tools.

    Args:
        request: FastAPI request

    Returns:
        Authenticated agent if present, None otherwise
    """
    return getattr(request.state, "mcp_agent", None)
