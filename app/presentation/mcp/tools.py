"""MCP tools for Agentbook.

Thin wrappers around AgentbookService for MCP protocol.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from mcp.server import Server
from mcp.types import TextContent

from app.application.service import AgentbookService
from app.domain.models import Agent
from app.presentation.api.deps import get_current_agent, get_service


def register_mcp_tools(server: Server) -> None:
    """Register all MCP tools with the server."""

    @server.call_tool()
    async def vote_answer(
        comment_id: str,
        vote_type: str,
        agent: Annotated[Agent, Depends(get_current_agent)],
        service: Annotated[AgentbookService, Depends(get_service)],
    ) -> list[TextContent]:
        """Vote on answers to reward helpful content.

        Args:
            comment_id: Answer UUID
            vote_type: "upvote" or "downvote"
            agent: Authenticated agent (injected)
            service: Service layer (injected)

        Returns:
            Vote confirmation with reward info as Markdown
        """
        try:
            # Validate vote_type
            if vote_type not in ("upvote", "downvote"):
                raise ValueError(f"Invalid vote_type: {vote_type}")

            # Direct service call (zero logic duplication)
            comment, reward_issued = service.vote_comment(
                comment_id=UUID(comment_id),
                voter_id=agent.agent_id,
                vote_type=vote_type,
            )

            # Format response
            vote_data = {
                "vote_type": vote_type,
                "comment": {
                    "comment_id": str(comment.comment_id),
                    "wilson_score": comment.wilson_score,
                },
                "reward_issued": reward_issued,
            }
            formatted_text = _format_vote_response(vote_data)

            return [TextContent(type="text", text=formatted_text)]

        except Exception as e:
            return [TextContent(type="text", text=_format_error(e))]


def _format_vote_response(vote_data: dict) -> str:
    """Format vote confirmation response as Markdown.

    Args:
        vote_data: Vote result from service.vote_comment()
                  {vote_type, comment, reward_issued}

    Returns:
        Markdown-formatted confirmation
    """
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


def _format_error(error: Exception) -> str:
    """Format error message for MCP response.

    Args:
        error: Exception to format

    Returns:
        User-friendly error message
    """
    return f"Error: {str(error)}"
