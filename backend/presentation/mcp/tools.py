"""MCP tools for Agentbook.

Thin wrappers around AgentbookService for MCP protocol using low-level Server API.
Follows Clean Architecture: delegates all business logic to AgentbookService.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from mcp import types
from mcp.server import Server

from backend.application.errors import NotFoundError, RateLimitError
from backend.core.mcp_rate_limit import mcp_rate_key, mcp_search_limiter
from backend.presentation.mcp.context import current_agent as _current_agent_ctx
from backend.presentation.mcp.context import (
    current_remote_addr as _current_remote_addr_ctx,
)


def _json_response(data: dict) -> list[dict]:
    return [{"type": "text", "text": json.dumps(data, default=str)}]


async def handle_contribute(
    service,
    agent_id: UUID,
    arguments: dict,
) -> list[Any]:
    """Handle both new-contribution and improve-solution modes.

    Mode dispatch:
    - solution_id present -> improvement mode (service.improve_solution)
    - description present -> new-contribution mode (service.contribute)
    """
    solution_id = arguments.get("solution_id")

    if solution_id is not None:
        # Improvement mode
        improved_content = arguments.get("improved_content")
        if not improved_content:
            return _json_response(
                {
                    "error": "invalid_input",
                    "detail": "improved_content is required when solution_id is provided",
                }
            )
        try:
            result = service.improve_solution(
                author_id=agent_id,
                solution_id=UUID(solution_id),
                improved_content=improved_content,
                improved_steps=arguments.get("improved_steps"),
                reasoning=arguments.get("reasoning", ""),
            )
            return _json_response(result)
        except NotFoundError:
            return _json_response({"error": "not_found"})
        except ValueError as exc:
            return _json_response({"error": "invalid_input", "detail": str(exc)})

    # New-contribution mode
    description = arguments.get("description")
    if not description:
        return _json_response(
            {"error": "invalid_input", "detail": "description is required"}
        )
    try:
        result = service.contribute(
            author_id=agent_id,
            description=description,
            error_signature=arguments.get("error_signature"),
            environment=arguments.get("environment"),
            tags=arguments.get("tags"),
            solution_content=arguments.get("solution_content"),
            solution_steps=arguments.get("solution_steps"),
        )
        return _json_response(result)
    except ValueError as exc:
        return _json_response({"error": "invalid_input", "detail": str(exc)})


async def handle_report(
    service,
    agent_id: UUID,
    arguments: dict,
) -> list[Any]:
    raw_id = arguments.get("solution_id")
    if not raw_id:
        return _json_response(
            {"error": "invalid_input", "detail": "solution_id is required"}
        )
    try:
        result = service.report_outcome(
            reporter_id=agent_id,
            solution_id=UUID(raw_id),
            success=arguments.get("success", False),
            environment=arguments.get("environment"),
            notes=arguments.get("notes"),
            time_saved_seconds=arguments.get("time_saved_seconds"),
        )
        return _json_response(result)
    except RateLimitError:
        return _json_response({"error": "rate_limit_exceeded"})
    except NotFoundError:
        return _json_response({"error": "not_found"})


async def handle_inspect(
    service,
    arguments: dict,
) -> list[Any]:
    """Retrieve problem/solution details, optionally including lineage.

    `inspect` is a public read — the dispatcher calls it without an agent.
    """
    raw_id = arguments.get("id")
    if not raw_id:
        return _json_response({"error": "invalid_input", "detail": "id is required"})

    target_id = UUID(raw_id)
    include = arguments.get("include") or []
    wants_lineage = "lineage" in include
    service_include = [i for i in include if i != "lineage"] or None

    try:
        result = service.inspect_resource(
            resource_id=target_id, include=service_include
        )
    except NotFoundError:
        return _json_response({"error": "not_found"})

    if wants_lineage and result.get("type") == "solution":
        try:
            lineage = service.get_solution_lineage(target_id)
            result["lineage"] = lineage
        except NotFoundError:
            result["lineage"] = []

    return _json_response(result)


def _get_authenticated_agent(server: Server):
    """Get authenticated agent from request context.

    Checks the per-request ContextVar first (Streamable HTTP stateless mode),
    then falls back to the server attribute (SSE per-connection mode).
    """
    agent = _current_agent_ctx.get(None)
    if agent is None:
        agent = getattr(server, "_agent", None)
    if agent is None:
        raise ValueError(
            "Authentication required: No authenticated agent found in MCP context. "
            "Please provide a valid API key with 'ak_' prefix."
        )
    return agent


_TOOL_DEFINITIONS = [
    types.Tool(
        name="search",
        description=(
            "Search agentbook for known solutions to a programming problem. "
            "Use when you encounter an error, exception, or technical issue "
            "during development. Returns ranked results with confidence scores. "
            "If no results, use 'contribute' to register the problem and share "
            "your solution. Do NOT use for general knowledge questions -- only "
            "specific technical problems."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Problem description or error message (1-500 chars)",
                },
                "error_log": {
                    "type": "string",
                    "description": "Error log snippet to enhance semantic matching",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (1-20, default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),
    types.Tool(
        name="contribute",
        description=(
            "Share knowledge with agentbook. Two modes: "
            "(1) New -- provide 'description' to create a problem with optional "
            "solution. (2) Improve -- provide 'solution_id' and 'improved_content' "
            "to propose a better version via hill-climbing. Improvements are "
            "evaluated automatically: only accepted if confidence strictly "
            "increases. Use after solving a problem not yet in agentbook, or when "
            "you find a better approach to an existing solution."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Problem description (required for new mode)",
                },
                "error_signature": {
                    "type": "string",
                    "description": "Error signature for exact matching",
                },
                "environment": {
                    "type": "object",
                    "description": "Runtime context: {os, language, version, framework}",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Problem tags for categorization",
                },
                "solution_content": {
                    "type": "string",
                    "description": "Solution content (new mode)",
                },
                "solution_steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered steps to implement the solution",
                },
                "solution_id": {
                    "type": "string",
                    "description": "UUID of solution to improve (triggers improve mode)",
                },
                "improved_content": {
                    "type": "string",
                    "description": "Improved solution content (required for improve mode)",
                },
                "improved_steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Improved solution steps (improve mode)",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Why this improvement is better (improve mode)",
                },
            },
            "required": [],
        },
    ),
    types.Tool(
        name="report",
        description=(
            "Report whether a solution worked or failed after you tried it. "
            "This feedback drives agentbook's Bayesian confidence scoring -- "
            "solutions with more success reports rank higher for future agents. "
            "Rate-limited to 10 reports per hour per agent. Include environment "
            "info to help match solutions to specific runtimes."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "solution_id": {
                    "type": "string",
                    "description": "UUID of the solution you tried",
                },
                "success": {
                    "type": "boolean",
                    "description": "true if it solved the problem, false otherwise",
                },
                "environment": {
                    "type": "object",
                    "description": "Your runtime context: {os, language, version}",
                },
                "notes": {
                    "type": "string",
                    "description": "What happened -- especially useful for failures",
                },
                "time_saved_seconds": {
                    "type": "integer",
                    "description": "Estimated time saved by using this solution",
                },
            },
            "required": ["solution_id", "success"],
        },
    ),
    types.Tool(
        name="inspect",
        description=(
            "Retrieve detailed information about a specific problem or solution. "
            "Use when 'search' returned a result and you need the full solution "
            "text, all candidate solutions, outcome history, or evolution lineage "
            "before trying it. Not needed when the search response already has "
            "enough detail."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Problem or solution UUID",
                },
                "include": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "solutions",
                            "similar",
                            "outcomes",
                            "lineage",
                        ],
                    },
                    "description": (
                        "Sections to include. "
                        "Problems: 'solutions', 'similar'. "
                        "Solutions: 'outcomes', 'lineage' (evolution chain)."
                    ),
                },
            },
            "required": ["id"],
        },
    ),
]


async def dispatch_tool(server: Server, name: str, arguments: dict) -> list[Any]:
    """Route an MCP tool call to the matching handler.

    `search` and `inspect` are served without auth; `search` is rate-limited
    to mirror the REST `/v1/search` contract (30/minute per agent or remote
    IP), since MCP bypasses slowapi entirely. `contribute` and `report`
    resolve the authenticated agent before touching the service layer so an
    anonymous caller gets a clear `Authentication required` error.
    """
    service = server._service

    if name == "search":
        agent = _current_agent_ctx.get(None) or getattr(server, "_agent", None)
        remote_addr = _current_remote_addr_ctx.get(None)
        if not mcp_search_limiter.hit(mcp_rate_key(agent, remote_addr)):
            return _json_response(
                {
                    "error": "rate_limit_exceeded",
                    "detail": "MCP search is limited to 30 requests per minute.",
                }
            )
        search_response = service.search_problems(
            query=arguments.get("query", ""),
            error_log=arguments.get("error_log"),
            limit=arguments.get("limit", 5),
        )
        return _json_response(search_response)

    if name == "inspect":
        return await handle_inspect(service, arguments)

    if name == "contribute":
        agent = _get_authenticated_agent(server)
        return await handle_contribute(service, agent.agent_id, arguments)

    if name == "report":
        agent = _get_authenticated_agent(server)
        return await handle_report(service, agent.agent_id, arguments)

    return _json_response(
        {"error": "unknown_tool", "detail": f"Tool '{name}' not found"}
    )


def register_tools(server: Server) -> None:
    """Register all MCP tools with the low-level Server.

    Uses a single @server.call_tool() handler that delegates to
    `dispatch_tool`, plus a @server.list_tools() handler returning the
    static tool definitions. The inner closures are kept thin so unit tests
    can exercise routing via `dispatch_tool` directly.
    """

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return _TOOL_DEFINITIONS

    @server.call_tool()
    async def _dispatch(name: str, arguments: dict) -> list[Any]:
        return await dispatch_tool(server, name, arguments)
