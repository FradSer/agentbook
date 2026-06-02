"""Authentication middleware for MCP (Model Context Protocol) endpoints.

Provides token verification and agent injection into MCP context.
Follows Clean Architecture: delegates verification to AgentbookService.
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from backend.application.errors import UnauthorizedError
from backend.application.service import AgentbookService
from backend.core.auth import BearerErrorKind, parse_bearer_token
from backend.domain.models import Agent


class AuthFailure(StrEnum):
    """Why MCP credential resolution failed, surfaced as the tool-error detail.

    The dispatcher maps each cause to a distinct message so an agent runtime
    can tell "you sent no key" from "your key is wrong" from "your header is
    malformed" — without the message ever revealing whether a given account
    exists.
    """

    NO_CREDENTIALS = "no_credentials"
    INVALID_KEY = "invalid_key"
    MALFORMED_BEARER = "malformed_bearer"


# Detail messages keyed by failure cause. Kept here (not in the dispatcher) so
# the credential-parsing layer owns the human-readable contract.
AUTH_FAILURE_DETAILS: dict[AuthFailure, str] = {
    AuthFailure.NO_CREDENTIALS: "Authentication required: no credentials provided",
    AuthFailure.INVALID_KEY: "Invalid or revoked API key",
    AuthFailure.MALFORMED_BEARER: "Malformed Authorization header: expected Bearer",
}


# Per-request cause of an MCP auth failure. ``None`` means either authenticated
# or no attempt yet; the dispatcher falls back to NO_CREDENTIALS in that case so
# an anonymous write attempt still reports the honest "no credentials" detail.
current_auth_error: ContextVar[AuthFailure | None] = ContextVar(
    "mcp_current_auth_error", default=None
)


def resolve_mcp_credentials(
    service: AgentbookService,
    authorization: str | None,
    *,
    api_key_prefix: str = "ak_",
) -> tuple[Agent | None, AuthFailure | None]:
    """Resolve an Authorization header into ``(agent, failure)``.

    Exactly one element is populated: a verified ``Agent`` on success, or an
    ``AuthFailure`` naming the cause. A missing header and a wrong-prefix /
    wrong-scheme header are reported distinctly so the dispatcher can emit the
    differentiated detail; a syntactically valid but unknown/revoked key maps to
    ``INVALID_KEY`` without leaking whether the account ever existed.
    """
    if authorization is None or not authorization.strip():
        return None, AuthFailure.NO_CREDENTIALS

    parsed = parse_bearer_token(authorization, required_prefix=api_key_prefix)
    if not parsed.ok:
        if parsed.error_kind == BearerErrorKind.MISSING_HEADER:
            return None, AuthFailure.NO_CREDENTIALS
        return None, AuthFailure.MALFORMED_BEARER

    try:
        agent = service.authenticate(api_key=parsed.token, agent_info=None)
    except UnauthorizedError:
        return None, AuthFailure.INVALID_KEY
    return agent, None


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
