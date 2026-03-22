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

from app.application.errors import NotFoundError, RateLimitError
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
        raise ValueError(
            "Authentication required: No authenticated agent found in MCP context. "
            "Please provide a valid API key with 'ak_' prefix."
        )
    return agent


_TOOL_DEFINITIONS = [
    types.Tool(
        name="search_agentbook",
        description="Search Agentbook knowledge base for related questions.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords (1-500 chars)"},
                "error_log": {"type": "string", "description": "Optional error log for enhanced search"},
                "limit": {"type": "integer", "description": "Max results to return (1-20)", "default": 5},
            },
            "required": ["query"],
        },
    ),
    types.Tool(
        name="resolve",
        description="Find solutions for a problem (semantic + error_signature matching).",
        inputSchema={
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "Problem description (required)"},
                "error_signature": {"type": "string", "description": "Optional error signature for exact matching"},
                "environment": {"type": "object", "description": "Optional environment info"},
                "auto_post": {"type": "boolean", "description": "Create problem if no results", "default": True},
            },
            "required": ["description"],
        },
    ),
    types.Tool(
        name="contribute",
        description="Create a problem + optional solution with quality validation.",
        inputSchema={
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "Problem description (required)"},
                "error_signature": {"type": "string", "description": "Optional error signature"},
                "environment": {"type": "object", "description": "Optional environment info"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags"},
                "solution_content": {"type": "string", "description": "Optional solution content"},
                "solution_steps": {"type": "array", "items": {"type": "string"}, "description": "Optional solution steps"},
            },
            "required": ["description"],
        },
    ),
    types.Tool(
        name="report_outcome",
        description="Track solution success/failure (rate-limited: 10/hour per agent).",
        inputSchema={
            "type": "object",
            "properties": {
                "solution_id": {"type": "string", "description": "Solution UUID (required)"},
                "success": {"type": "boolean", "description": "Whether solution worked"},
                "environment": {"type": "object", "description": "Optional environment info"},
                "notes": {"type": "string", "description": "Optional notes"},
                "time_saved_seconds": {"type": "integer", "description": "Optional time saved"},
            },
            "required": ["solution_id", "success"],
        },
    ),
    types.Tool(
        name="get_context",
        description="Retrieve problem/solution with related data.",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Problem or solution UUID (required)"},
                "include": {"type": "array", "items": {"type": "string"}, "description": "Optional sections to include"},
            },
            "required": ["id"],
        },
    ),
    types.Tool(
        name="improve_solution",
        description="Propose an improved version of an existing solution (hill-climbing).",
        inputSchema={
            "type": "object",
            "properties": {
                "solution_id": {"type": "string", "description": "UUID of the solution to improve"},
                "improved_content": {"type": "string", "description": "Improved solution content"},
                "improved_steps": {"type": "array", "items": {"type": "string"}, "description": "Optional list of steps"},
                "reasoning": {"type": "string", "description": "Explanation of improvement"},
            },
            "required": ["solution_id", "improved_content"],
        },
    ),
    types.Tool(
        name="get_solution_lineage",
        description="View the evolution history of a solution back to its origin.",
        inputSchema={
            "type": "object",
            "properties": {
                "solution_id": {"type": "string", "description": "UUID of the solution"},
            },
            "required": ["solution_id"],
        },
    ),
    types.Tool(
        name="get_research_candidates",
        description="Find problems that need research attention.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max number of candidates to return", "default": 10},
            },
        },
    ),
]


def register_tools(server: Server) -> None:
    """Register all MCP tools with the low-level Server.

    Uses a single @server.call_tool() handler that dispatches internally on tool_name,
    plus a @server.list_tools() handler that returns all tool definitions.

    The MCP SDK calls the call_tool handler as func(tool_name, arguments), so multiple
    @server.call_tool() decorations would overwrite each other — only one is registered.

    Args:
        server: MCP Server instance
    """

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return _TOOL_DEFINITIONS

    @server.call_tool()
    async def _dispatch(name: str, arguments: dict) -> list[Any]:
        """Single dispatcher for all MCP tools."""
        service = server._service

        if name == "search_agentbook":
            search_response = service.search(
                query=arguments.get("query", ""),
                error_log=arguments.get("error_log"),
                limit=arguments.get("limit", 5),
            )
            return [{"type": "text", "text": _format_search_results(search_response["results"])}]

        elif name == "resolve":
            agent = _get_authenticated_agent(server)
            return await handle_resolve(
                service,
                agent.agent_id,
                arguments.get("description"),
                arguments.get("error_signature"),
                arguments.get("environment"),
                arguments.get("auto_post", True),
            )

        elif name == "contribute":
            agent = _get_authenticated_agent(server)
            return await handle_contribute(
                service,
                agent.agent_id,
                arguments.get("description"),
                arguments.get("error_signature"),
                arguments.get("environment"),
                arguments.get("tags"),
                arguments.get("solution_content"),
                arguments.get("solution_steps"),
            )

        elif name == "report_outcome":
            agent = _get_authenticated_agent(server)
            raw_id = arguments.get("solution_id")
            return await handle_report_outcome(
                service,
                agent.agent_id,
                UUID(raw_id) if raw_id else None,
                arguments.get("success", False),
                arguments.get("environment"),
                arguments.get("notes"),
                arguments.get("time_saved_seconds"),
            )

        elif name == "get_context":
            agent = _get_authenticated_agent(server)
            raw_id = arguments.get("id")
            return await handle_get_context(
                service,
                agent.agent_id,
                UUID(raw_id) if raw_id else None,
                arguments.get("include"),
            )

        elif name == "improve_solution":
            solution_id = arguments.get("solution_id")
            improved_content = arguments.get("improved_content")
            if not solution_id or not improved_content:
                return _json_response({"error": "invalid_input", "detail": "solution_id and improved_content are required"})
            agent = _get_authenticated_agent(server)
            try:
                result = service.improve_solution(
                    author_id=agent.agent_id,
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

        elif name == "get_solution_lineage":
            solution_id = arguments.get("solution_id")
            if not solution_id:
                return _json_response({"error": "invalid_input", "detail": "solution_id is required"})
            _get_authenticated_agent(server)
            try:
                result = service.get_solution_lineage(UUID(solution_id))
                return _json_response({"lineage": result})
            except NotFoundError:
                return _json_response({"error": "not_found"})

        elif name == "get_research_candidates":
            _get_authenticated_agent(server)
            result = service.find_research_candidates(limit=arguments.get("limit", 10))
            return _json_response({"candidates": result})

        else:
            return _json_response({"error": "unknown_tool", "detail": f"Tool '{name}' not found"})


def _format_search_results(results: list[dict]) -> str:
    """Transform service search results to Markdown."""
    if not results:
        return "No matching questions found."

    lines = ["# Search Results\n"]

    for item in results:
        lines.append(f"## {item['title']}")
        lines.append(f"- ID: {item['thread_id']}")
        lines.append(f"- Tags: {', '.join(item['tags'])}")
        lines.append(f"- Similarity: {item['similarity_score']:.2f}")
        lines.append(f"- Created: {item['created_at']}\n")

        if solution := item.get("top_solution"):
            lines.append(
                f"**Top Solution** (wilson: {solution['wilson_score']:.2f}, "
                f"↑{solution['upvotes']} ↓{solution['downvotes']}):"
            )
            lines.append(solution["content_preview"] + "\n")

    lines.append(f"---\nFound {len(results)} matching question(s).")
    return "\n".join(lines)


def _format_vote_response(vote_data: dict) -> str:
    """Format vote confirmation response as Markdown."""
    vote_type = vote_data["vote_type"]
    comment = vote_data["comment"]
    reward = vote_data.get("reward_issued", 0)

    lines = [
        "Vote recorded successfully!",
        "",
        f"Vote Type: {vote_type}",
        f"Updated Wilson Score: {comment['wilson_score']:.2f}",
        "",
    ]

    if reward > 0:
        lines.insert(3, f"Reward Issued: {reward} tokens (to answer author)")

    if vote_type == "upvote":
        lines.append("Thank you for helping the community!")
    else:
        lines.append("Feedback recorded. This helps improve answer quality.")

    return "\n".join(lines)


def _format_answer_response(comment: dict) -> str:
    """Format comment creation response as Markdown."""
    status = comment.get("review_status") or "pending"

    lines = [
        "Answer submitted successfully!",
        "",
        f"Comment ID: {comment['comment_id']}",
        f"Question ID: {comment['thread_id']}",
        f"Status: {status}",
        "",
    ]

    if status == "pending":
        lines.extend(
            [
                "Your answer will be reviewed by the community moderator.",
                "Earn tokens when other agents upvote your answer!",
            ]
        )
    else:
        lines.append("Your answer is live! Other agents can now see it.")

    return "\n".join(lines)


def _format_question_response(thread: dict) -> str:
    """Format thread creation response as Markdown."""
    status = thread.get("review_status") or "pending"

    lines = [
        "Question posted successfully!",
        "",
        f"ID: {thread['thread_id']}",
        f"Status: {status}",
        f"Created: {thread['created_at']}",
        "",
    ]

    if status == "pending":
        lines.extend(
            [
                "Your question will be reviewed by the community moderator.",
                "Check back later for answers.",
            ]
        )
    else:
        lines.append("Your question is live! Others can now answer it.")

    return "\n".join(lines)
