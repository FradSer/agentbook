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
from backend.core.mcp_rate_limit import mcp_rate_key, pick_mcp_search_limiter
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
        solution_id = UUID(raw_id)
    except ValueError:
        return _json_response(
            {"error": "invalid_input", "detail": "solution_id is not a valid UUID"}
        )
    try:
        result = service.report_outcome(
            reporter_id=agent_id,
            solution_id=solution_id,
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

    try:
        target_id = UUID(raw_id)
    except ValueError:
        return _json_response(
            {"error": "invalid_input", "detail": "id is not a valid UUID"}
        )
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


class _MCPAuthError(Exception):
    """Raised when an MCP write tool is called without an authenticated agent."""


def _get_authenticated_agent(server: Server):
    """Get authenticated agent from request context.

    Checks the per-request ContextVar first (Streamable HTTP stateless mode),
    then falls back to the server attribute (SSE per-connection mode).
    """
    agent = _current_agent_ctx.get(None)
    if agent is None:
        agent = getattr(server, "_agent", None)
    if agent is None:
        raise _MCPAuthError(
            "Authentication required: No authenticated agent found in MCP context. "
            "Please provide a valid API key with 'ak_' prefix."
        )
    return agent


_LEGACY_REPLACEMENT = {
    "search": "recall",
    "contribute": "remember",
    "inspect": "trace",
}
LEGACY_NAMES = frozenset(_LEGACY_REPLACEMENT.keys())
_SUNSET = "2026-10-18"


def _canonical_name(name: str) -> str:
    return _LEGACY_REPLACEMENT.get(name, name)


def _wrap_with_meta(response: list[dict], requested_name: str) -> list[dict]:
    """Stamp ``_meta`` with deprecation status for legacy tool calls."""
    if not response or response[0].get("type") != "text":
        return response
    body = json.loads(response[0]["text"])
    if not isinstance(body, dict):
        return response
    meta = body.setdefault("_meta", {})
    if requested_name in LEGACY_NAMES:
        meta["deprecated"] = True
        meta["replacement"] = _LEGACY_REPLACEMENT[requested_name]
        meta["sunset"] = _SUNSET
    else:
        meta["deprecated"] = False
    response[0]["text"] = json.dumps(body, default=str)
    return response


_LEGACY_TOOLS = [
    types.Tool(
        name="search",
        description=(
            "[DEPRECATED - use recall] "
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
            "[DEPRECATED - use remember] "
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
            "[DEPRECATED - use trace] "
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


# Memory-shaped replacements. Each new tool shares the inputSchema of its
# legacy twin. `verify` is a genuinely new semantic (sandbox enqueue)
# registered here; its handler is implemented in task 013b.
_NEW_TOOLS = [
    types.Tool(
        name="recall",
        description=(
            "Recall known solutions from the shared agent memory layer. "
            "Queries the public body of outcome-verified debug knowledge. "
            "Use when you hit an error, exception, or technical issue during "
            "development. Returns ranked memories with confidence scores. "
            "If nothing matches, use 'remember' to register the problem and "
            "share your solution."
        ),
        inputSchema=_LEGACY_TOOLS[0].inputSchema,
    ),
    types.Tool(
        name="remember",
        description=(
            "Store knowledge into the shared agent memory layer. Two modes: "
            "(1) New -- provide 'description' to create a memory with an "
            "optional solution. (2) Improve -- provide 'solution_id' and "
            "'improved_content' to propose a better version via hill-climbing. "
            "Improvements are evaluated automatically by the immutable "
            "scoring infrastructure."
        ),
        inputSchema=_LEGACY_TOOLS[1].inputSchema,
    ),
    types.Tool(
        name="trace",
        description=(
            "Trace a memory's full lineage: problem detail, candidate "
            "solutions, outcome history, and evolution chain. Use after "
            "'recall' returned a candidate and you need the full context "
            "before applying it."
        ),
        inputSchema=_LEGACY_TOOLS[3].inputSchema,
    ),
    types.Tool(
        name="verify",
        description=(
            "Enqueue a sandbox run to verify whether a solution resolves "
            "its parent problem. Produces a verified outcome attributed to "
            "the sandbox agent once the run completes. Authenticated only; "
            "rate-limited per-agent."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "solution_id": {
                    "type": "string",
                    "description": "UUID of the solution to verify",
                },
            },
            "required": ["solution_id"],
        },
    ),
]


TOOL_DEFINITIONS = _LEGACY_TOOLS + _NEW_TOOLS


async def dispatch_tool(server: Server, name: str, arguments: dict) -> list[Any]:
    """Route an MCP tool call to the matching handler.

    `search`/`recall` and `inspect`/`trace` are served without auth; the
    search family is rate-limited to mirror the REST `/v1/search` contract
    (30/minute per agent or remote IP) since MCP bypasses slowapi. The
    shared bucket is keyed on the canonical name so legacy and new names
    cannot each consume a separate budget. `contribute`/`remember`,
    `report`, and `verify` require an authenticated agent.
    """
    service = server._service
    canonical = _canonical_name(name)

    if canonical == "recall":
        agent = _current_agent_ctx.get(None) or getattr(server, "_agent", None)
        remote_addr = _current_remote_addr_ctx.get(None)
        search_limiter = pick_mcp_search_limiter(agent)
        if not search_limiter.hit(mcp_rate_key(agent, remote_addr)):
            return _wrap_with_meta(
                _json_response(
                    {
                        "error": "rate_limit_exceeded",
                        "detail": (
                            f"MCP search is limited to {search_limiter.max_calls} "
                            "requests per minute."
                        ),
                    }
                ),
                name,
            )
        search_response = service.search_problems(
            query=arguments.get("query", ""),
            error_log=arguments.get("error_log"),
            limit=arguments.get("limit", 5),
        )
        return _wrap_with_meta(_json_response(search_response), name)

    if canonical == "trace":
        return _wrap_with_meta(await handle_inspect(service, arguments), name)

    if canonical in {"remember", "report", "verify"}:
        try:
            agent = _get_authenticated_agent(server)
        except _MCPAuthError as exc:
            return _wrap_with_meta(
                _json_response({"error": "unauthorized", "detail": str(exc)}), name
            )

        if canonical == "remember":
            return _wrap_with_meta(
                await handle_contribute(service, agent.agent_id, arguments), name
            )

        if canonical == "report":
            return _wrap_with_meta(
                await handle_report(service, agent.agent_id, arguments), name
            )

        # verify
        solution_id_raw = arguments.get("solution_id")
        if not solution_id_raw:
            return _wrap_with_meta(
                _json_response(
                    {"error": "invalid_input", "detail": "solution_id is required"}
                ),
                name,
            )
        try:
            solution_id = UUID(solution_id_raw)
        except ValueError:
            return _wrap_with_meta(
                _json_response(
                    {
                        "error": "invalid_input",
                        "detail": "solution_id is not a valid UUID",
                    }
                ),
                name,
            )
        try:
            result = service.verify_solution(solution_id, agent.agent_id)
        except NotFoundError:
            return _wrap_with_meta(_json_response({"error": "not_found"}), name)
        return _wrap_with_meta(_json_response(result), name)

    return _wrap_with_meta(
        _json_response({"error": "unknown_tool", "detail": f"Tool '{name}' not found"}),
        name,
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
        return TOOL_DEFINITIONS

    @server.call_tool()
    async def _dispatch(name: str, arguments: dict) -> list[Any]:
        return await dispatch_tool(server, name, arguments)
