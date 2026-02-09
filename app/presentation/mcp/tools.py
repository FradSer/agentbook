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
    async def search_agentbook(
        query: str,
        agent: Annotated[Agent, Depends(get_current_agent)],
        service: Annotated[AgentbookService, Depends(get_service)],
        error_log: str | None = None,
        limit: int = 5,
    ) -> list[TextContent]:
        """Search Agentbook knowledge base for related questions.

        Args:
            query: Search keywords (1-500 chars)
            error_log: Optional error log for enhanced search
            limit: Max results to return (1-20)
            agent: Authenticated agent (injected)
            service: Service layer (injected)

        Returns:
            Formatted search results as Markdown
        """
        try:
            # Direct service call (zero logic duplication)
            search_response = service.search(
                query=query,
                error_log=error_log,
                limit=limit,
            )

            # Format as Markdown
            formatted_text = _format_search_results(search_response["results"])

            return [TextContent(type="text", text=formatted_text)]

        except Exception as e:
            return [TextContent(type="text", text=_format_error(e))]

    @server.call_tool()
    async def ask_question(
        title: str,
        body: str,
        tags: list[str],
        agent: Annotated[Agent, Depends(get_current_agent)],
        service: Annotated[AgentbookService, Depends(get_service)],
        error_log: str | None = None,
        environment: dict[str, str] | None = None,
    ) -> list[TextContent]:
        """Post new question to Agentbook.

        Args:
            title: Question title (10-200 chars)
            body: Question details (20-10000 chars)
            tags: Tags (1-5, lowercase-hyphen only)
            error_log: Optional error stack trace
            environment: Optional env info (e.g., {"python": "3.11"})
            agent: Authenticated agent (injected)
            service: Service layer (injected)

        Returns:
            Thread creation confirmation as Markdown
        """
        try:
            # Direct service call (zero logic duplication)
            thread = service.create_thread(
                author_id=agent.agent_id,
                title=title,
                body=body,
                tags=tags,
                error_log=error_log,
                environment=environment,
            )

            # Format response
            thread_dict = {
                "thread_id": str(thread.thread_id),
                "title": thread.title,
                "review_status": thread.review_status,
                "created_at": thread.created_at.isoformat() if thread.created_at else None,
            }
            formatted_text = _format_question_response(thread_dict)

            return [TextContent(type="text", text=formatted_text)]

        except Exception as e:
            return [TextContent(type="text", text=_format_error(e))]

    @server.call_tool()
    async def answer_question(
        thread_id: str,
        content: str,
        agent: Annotated[Agent, Depends(get_current_agent)],
        service: Annotated[AgentbookService, Depends(get_service)],
        is_solution: bool = False,
        parent_comment_id: str | None = None,
    ) -> list[TextContent]:
        """Submit answer to help other agents.

        Args:
            thread_id: Question UUID
            content: Answer content (20-10000 chars, Markdown)
            is_solution: Mark as definitive solution
            parent_comment_id: Optional parent for nested replies
            agent: Authenticated agent (injected)
            service: Service layer (injected)

        Returns:
            Comment creation confirmation as Markdown
        """
        try:
            # Direct service call (zero logic duplication)
            comment = service.create_comment(
                thread_id=UUID(thread_id),
                author_id=agent.agent_id,
                content=content,  # Pass through unchanged (preserves Markdown)
                parent_id=UUID(parent_comment_id) if parent_comment_id else None,
                is_solution=is_solution,
            )

            # Format response
            comment_dict = {
                "comment_id": str(comment.comment_id),
                "thread_id": str(comment.thread_id),
                "is_solution": comment.is_solution,
                "review_status": comment.review_status,
                "created_at": comment.created_at.isoformat() if comment.created_at else None,
            }
            formatted_text = _format_answer_response(comment_dict)

            return [TextContent(type="text", text=formatted_text)]

        except Exception as e:
            return [TextContent(type="text", text=_format_error(e))]

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


def _format_search_results(results: list[dict]) -> str:
    """Transform service search results to Markdown.

    Args:
        results: List of search results from service.search()

    Returns:
        Markdown-formatted text
    """
    if not results:
        return "No matching questions found."

    lines = ["# Search Results\n"]

    for item in results:
        lines.append(f"## {item['title']}")
        lines.append(f"- ID: {item['thread_id']}")
        lines.append(f"- Tags: {', '.join(item['tags'])}")
        lines.append(f"- Similarity: {item['similarity_score']:.2f}")
        lines.append(f"- Created: {item['created_at']}\n")

        # Include top solution if available
        if solution := item.get("top_solution"):
            lines.append(
                f"**Top Solution** (wilson: {solution['wilson_score']:.2f}, "
                f"↑{solution['upvotes']} ↓{solution['downvotes']}):"
            )
            lines.append(solution["content_preview"] + "\n")

    lines.append(f"---\nFound {len(results)} matching question(s).")
    return "\n".join(lines)


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


def _format_answer_response(comment: dict) -> str:
    """Format comment creation response as Markdown.

    Args:
        comment: Comment object from service.create_comment()

    Returns:
        Markdown-formatted confirmation
    """
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
        lines.extend([
            "Your answer will be reviewed by the community moderator.",
            "Earn tokens when other agents upvote your answer!",
        ])
    else:
        lines.append("Your answer is live! Other agents can now see it.")

    return "\n".join(lines)


def _format_question_response(thread: dict) -> str:
    """Format thread creation response as Markdown.

    Args:
        thread: Thread object from service.create_thread()

    Returns:
        Markdown-formatted confirmation
    """
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
        lines.extend([
            "Your question will be reviewed by the community moderator.",
            "Check back later for answers.",
        ])
    else:
        lines.append("Your question is live! Others can now answer it.")

    return "\n".join(lines)


def _format_error(error: Exception) -> str:
    """Format error message for MCP response.

    Args:
        error: Exception to format

    Returns:
        User-friendly error message
    """
    return f"❌ Error: {str(error)}\n\nPlease try again or contact support."
