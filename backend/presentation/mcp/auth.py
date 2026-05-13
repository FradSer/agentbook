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

from backend.application.errors import UnauthorizedError
from backend.application.service import AgentbookService
from backend.core.auth import parse_bearer_token
from backend.domain.models import Agent


@dataclass(frozen=True, slots=True)
class TokenVerifier:
    """Verifies authentication tokens for MCP endpoints.

    Requires Bearer tokens in Authorization header.
    """

    service: AgentbookService
    api_key_prefix: str = "ak_"

    def verify(
        self,
        authorization: str | None = None,
    ) -> Agent:
        """Verify authentication token and return authenticated agent.

        Args:
            authorization: Bearer token from Authorization header

        Returns:
            Authenticated agent

        Raises:
            HTTPException: If authentication fails (401)
        """
        parsed = parse_bearer_token(authorization, required_prefix=self.api_key_prefix)
        if not parsed.ok:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication required: {parsed.detail}",
            )

        try:
            return self.service.authenticate(api_key=parsed.token, agent_info=None)
        except UnauthorizedError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(error),
            ) from error


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
        try:
            if authorization:
                agent = verifier.verify(authorization=authorization)
                request.state.mcp_agent = agent
        except HTTPException:
            pass

        return await call_next(request)
