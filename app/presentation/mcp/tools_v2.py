"""MCP v2 tools for Agentbook.

Handler functions are separated from MCP registration so they can be
tested directly without going through the MCP server protocol.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from mcp.server import Server

from app.application.errors import NotFoundError, RateLimitError, SelfReportError
from app.presentation.mcp.context import current_agent as _current_agent_ctx


def _json_response(data: dict) -> list[dict]:
    return [{"type": "text", "text": json.dumps(data, default=str)}]


async def handle_resolve(
    service,
    agent_id: UUID,
    description: str | None = None,
    error_signature: str | None = None,
    environment: dict | None = None,
    auto_post: bool = True,
) -> list[Any]:
    if not description:
        return _json_response({"error": "invalid_input", "detail": "description is required"})
    try:
        result = service.resolve(
            agent_id=agent_id,
            description=description,
            error_signature=error_signature,
            environment=environment,
            auto_post=auto_post,
        )
        return _json_response(result)
    except ValueError as exc:
        return _json_response({"error": "invalid_input", "detail": str(exc)})


async def handle_contribute(
    service,
    agent_id: UUID,
    description: str | None = None,
    error_signature: str | None = None,
    environment: dict | None = None,
    tags: list[str] | None = None,
    solution_content: str | None = None,
    solution_steps: list[str] | None = None,
    author_verified: bool = False,
) -> list[Any]:
    if not description:
        return _json_response({"error": "invalid_input", "detail": "description is required"})
    try:
        result = service.contribute(
            author_id=agent_id,
            description=description,
            error_signature=error_signature,
            environment=environment,
            tags=tags,
            solution_content=solution_content,
            solution_steps=solution_steps,
            author_verified=author_verified,
        )
        return _json_response(result)
    except ValueError as exc:
        return _json_response({"error": "invalid_input", "detail": str(exc)})


async def handle_report_outcome(
    service,
    agent_id: UUID,
    solution_id: UUID | None = None,
    success: bool = False,
    environment: dict | None = None,
    notes: str | None = None,
    time_saved_seconds: int | None = None,
) -> list[Any]:
    if solution_id is None:
        return _json_response({"error": "invalid_input", "detail": "solution_id is required"})
    try:
        result = service.report_outcome(
            reporter_id=agent_id,
            solution_id=solution_id,
            success=success,
            environment=environment,
            notes=notes,
            time_saved_seconds=time_saved_seconds,
        )
        return _json_response(result)
    except SelfReportError:
        return _json_response({"error": "self_reporting_not_allowed"})
    except RateLimitError:
        return _json_response({"error": "rate_limit_exceeded"})
    except NotFoundError:
        return _json_response({"error": "not_found"})


async def handle_get_context(
    service,
    agent_id: UUID,
    id: UUID | None = None,
    include: list[str] | None = None,
) -> list[Any]:
    if id is None:
        return _json_response({"error": "invalid_input", "detail": "id is required"})
    try:
        result = service.get_context(id=id, include=include)
        return _json_response(result)
    except NotFoundError:
        return _json_response({"error": "not_found"})


def _get_authenticated_agent(server: Server):
    """Get authenticated agent from request context.

    Checks the per-request ContextVar first (Streamable HTTP stateless mode),
    then falls back to the server attribute (SSE per-connection mode).
    """
    agent = _current_agent_ctx.get(None)
    if agent is None:
        agent = getattr(server, "_agent", None)
    if agent is None:
        raise ValueError("Authentication required: no authenticated agent in MCP context")
    return agent


def register_tools_v2(server: Server) -> None:
    @server.call_tool()
    async def resolve(**kwargs) -> list[Any]:
        service = server._service_v2
        agent = _get_authenticated_agent(server)
        return await handle_resolve(service, agent.agent_id, **kwargs)

    @server.call_tool()
    async def contribute(**kwargs) -> list[Any]:
        service = server._service_v2
        agent = _get_authenticated_agent(server)
        return await handle_contribute(service, agent.agent_id, **kwargs)

    @server.call_tool()
    async def report_outcome(**kwargs) -> list[Any]:
        service = server._service_v2
        agent = _get_authenticated_agent(server)
        return await handle_report_outcome(service, agent.agent_id, **kwargs)

    @server.call_tool()
    async def get_context(**kwargs) -> list[Any]:
        service = server._service_v2
        agent = _get_authenticated_agent(server)
        return await handle_get_context(service, agent.agent_id, **kwargs)
