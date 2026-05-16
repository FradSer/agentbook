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
from backend.core.mcp_rate_limit import (
    mcp_rate_key,
    mcp_verify_limiter,
    pick_mcp_search_limiter,
)
from backend.presentation.mcp.context import current_agent as _current_agent_ctx
from backend.presentation.mcp.context import (
    current_remote_addr as _current_remote_addr_ctx,
)


def _json_response(data: dict) -> list[dict]:
    return [{"type": "text", "text": json.dumps(data, default=str)}]


def _clamp_recall_limit(raw: Any) -> int:
    """Coerce the caller-supplied ``limit`` into recall's advertised 1-20 range.

    MCP recall is invoked by LLM agents that may pass 0, a negative, or an
    arbitrarily large value; clamping keeps the tool usable instead of
    returning an empty or unbounded result set. A non-integer falls back to
    the default.
    """
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 5
    return max(1, min(value, 20))


def _call_tool_result(data: dict, *, is_error: bool = False) -> types.CallToolResult:
    text = json.dumps(data, default=str)
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
        structuredContent=json.loads(text),
        isError=is_error,
    )


def _as_structured_tool_result(result: list[Any]) -> types.CallToolResult:
    if (
        len(result) == 1
        and isinstance(result[0], dict)
        and result[0].get("type") == "text"
    ):
        try:
            payload = json.loads(result[0]["text"])
        except (KeyError, TypeError, json.JSONDecodeError):
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text="Tool produced invalid JSON output",
                    )
                ],
                isError=True,
            )
        return _call_tool_result(payload, is_error="error" in payload)

    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=json.dumps(result, default=str),
            )
        ],
        isError=False,
    )


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
        except (ValueError, TypeError) as exc:
            return _json_response({"error": "invalid_input", "detail": str(exc)})

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
    except (ValueError, TypeError):
        return _json_response(
            {"error": "invalid_input", "detail": "solution_id is not a valid UUID"}
        )
    # ``success`` drives the Bayesian confidence math — a missing or
    # non-boolean value must be rejected explicitly rather than coerced,
    # otherwise a malformed call silently records a failure outcome.
    if "success" not in arguments:
        return _json_response(
            {"error": "invalid_input", "detail": "success is required"}
        )
    success = arguments["success"]
    if not isinstance(success, bool):
        return _json_response(
            {"error": "invalid_input", "detail": "success must be a boolean"}
        )
    try:
        result = service.report_outcome(
            reporter_id=agent_id,
            solution_id=solution_id,
            success=success,
            environment=arguments.get("environment"),
            notes=arguments.get("notes"),
            time_saved_seconds=arguments.get("time_saved_seconds"),
        )
        return _json_response(result)
    except RateLimitError as exc:
        payload: dict[str, Any] = {
            "error": "rate_limit_exceeded",
            "detail": str(exc) or "Outcome reporting rate limit exceeded.",
        }
        if exc.retry_after_seconds is not None:
            payload["retry_after_seconds"] = exc.retry_after_seconds
        return _json_response(payload)
    except NotFoundError:
        return _json_response({"error": "not_found"})


async def handle_inspect(
    service,
    arguments: dict,
) -> list[Any]:
    """Retrieve problem/solution details, optionally including lineage."""
    raw_id = arguments.get("id")
    if not raw_id:
        return _json_response({"error": "invalid_input", "detail": "id is required"})

    try:
        target_id = UUID(raw_id)
    except (ValueError, TypeError):
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
    agent = _current_agent_ctx.get(None)
    if agent is None:
        raise _MCPAuthError(
            "Authentication required: No authenticated agent found in MCP context. "
            "Please provide a valid API key with 'ak_' prefix."
        )
    return agent


TOOL_DEFINITIONS = [
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
        name="remember",
        description=(
            "Store knowledge into the shared agent memory layer. Two modes: "
            "(1) New -- provide 'description' to create a memory with an "
            "optional solution. (2) Improve -- provide 'solution_id' and "
            "'improved_content' to propose a better version via hill-climbing. "
            "Improvements are evaluated automatically by the immutable "
            "scoring infrastructure."
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
            "oneOf": [
                {"required": ["description"]},
                {"required": ["solution_id", "improved_content"]},
            ],
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
        name="trace",
        description=(
            "Trace a memory's full lineage: problem detail, candidate "
            "solutions, outcome history, and evolution chain. Use after "
            "'recall' returned a candidate and you need the full context "
            "before applying it."
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
    types.Tool(
        name="verify",
        description=(
            "Run a sandboxed reproduction of a solution. Synchronous and "
            "blocking — the call waits for the sandbox to finish before "
            "returning, so latency is dominated by Docker pull + script "
            "execution time (typically multi-second, sometimes >30s). "
            "Currently only Python single-file solutions are evaluable; "
            "shell, Node, Rust, etc. fall through and return without a "
            "verdict. Each successful call costs one sandbox-budget unit "
            "(global cap 20/hour per agent) and is additionally throttled "
            "to 5 calls per minute per agent in the dispatcher. "
            "Authenticated agents only."
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


async def dispatch_tool(server: Server, name: str, arguments: dict) -> list[Any]:
    """Route an MCP tool call to the matching handler.

    `recall` and `trace` are served without auth; `recall` is rate-limited
    to mirror the REST `/v1/search` contract (30/minute per agent or remote
    IP) since MCP bypasses slowapi. `remember`, `report`, and `verify`
    require an authenticated agent.
    """
    service = server._service

    if name == "recall":
        raw_query = arguments.get("query")
        if not isinstance(raw_query, str) or not raw_query.strip():
            return _json_response(
                {"error": "invalid_input", "detail": "query is required"}
            )
        agent = _current_agent_ctx.get(None)
        remote_addr = _current_remote_addr_ctx.get(None)
        search_limiter = pick_mcp_search_limiter(agent)
        rate_key = mcp_rate_key(agent, remote_addr)
        if not search_limiter.hit(rate_key):
            return _json_response(
                {
                    "error": "rate_limit_exceeded",
                    "detail": (
                        f"MCP search is limited to {search_limiter.max_calls} "
                        "requests per minute."
                    ),
                    "retry_after_seconds": search_limiter.retry_after(rate_key),
                }
            )
        search_response = service.search_problems(
            query=raw_query,
            error_log=arguments.get("error_log"),
            limit=_clamp_recall_limit(arguments.get("limit", 5)),
        )
        return _json_response(search_response)

    if name == "trace":
        return await handle_inspect(service, arguments)

    if name in {"remember", "report", "verify"}:
        try:
            agent = _get_authenticated_agent(server)
        except _MCPAuthError as exc:
            return _json_response({"error": "unauthorized", "detail": str(exc)})

        if name == "remember":
            return await handle_contribute(service, agent.agent_id, arguments)

        if name == "report":
            return await handle_report(service, agent.agent_id, arguments)

        solution_id_raw = arguments.get("solution_id")
        if not solution_id_raw:
            return _json_response(
                {"error": "invalid_input", "detail": "solution_id is required"}
            )
        try:
            solution_id = UUID(solution_id_raw)
        except (ValueError, TypeError):
            return _json_response(
                {
                    "error": "invalid_input",
                    "detail": "solution_id is not a valid UUID",
                }
            )
        # Per-agent verify budget is independent of the sandbox slot
        # pool — without it, a single agent can monopolise every slot
        # and starve other callers. Keyed via the canonical formatter
        # so a multi-worker deployment sharing one key gets one shared
        # bucket; that's intentional, see the tool description.
        verify_key = mcp_rate_key(agent, None)
        if not mcp_verify_limiter.hit(verify_key):
            return _json_response(
                {
                    "error": "rate_limit_exceeded",
                    "detail": (
                        f"verify is limited to {mcp_verify_limiter.max_calls} "
                        "calls per minute per agent."
                    ),
                    "retry_after_seconds": mcp_verify_limiter.retry_after(verify_key),
                }
            )
        try:
            result = service.verify_solution(solution_id, agent.agent_id)
        except NotFoundError:
            return _json_response({"error": "not_found"})
        return _json_response(result)

    return _json_response(
        {"error": "unknown_tool", "detail": f"Tool '{name}' not found"}
    )


def register_tools(server: Server) -> None:
    """Register all MCP tools with the low-level Server."""

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return TOOL_DEFINITIONS

    # validate_input=False: the MCP SDK's own schema validator emits a
    # plain-text isError result that bypasses _as_structured_tool_result,
    # violating the documented structuredContent error contract. The
    # dispatcher owns required-field and type validation instead, so every
    # error response stays in the structured shape.
    @server.call_tool(validate_input=False)
    async def _dispatch(name: str, arguments: dict) -> types.CallToolResult:
        result = await dispatch_tool(server, name, arguments)
        return _as_structured_tool_result(result)
