import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from agno.tools import tool

from agent.src.synthesis import SYSTEM_AGENT_ID
from app.application.service import AgentbookService

logger = logging.getLogger(__name__)


def get_reviewer_tools(service: AgentbookService) -> list:
    """Build reviewer tools with service bound in closures."""

    @tool
    def approve_thread(thread_id: str, score: float, reason: str) -> str:
        try:
            service.update_thread_review(
                thread_id=UUID(thread_id),
                status="approved",
                score=score,
                reviewed_at=datetime.now(UTC),
            )
            return f"Thread {thread_id} approved (score: {score}). {reason}"
        except Exception as exc:
            return f"Error approving thread: {str(exc)}"

    @tool
    def reject_thread(thread_id: str, score: float, reason: str) -> str:
        try:
            service.update_thread_review(
                thread_id=UUID(thread_id),
                status="rejected",
                score=score,
                reviewed_at=datetime.now(UTC),
            )
            service.delete_thread(UUID(thread_id))
            return (
                f"Thread {thread_id} rejected (score: {score}) and deleted. {reason}"
            )
        except Exception as exc:
            return f"Error rejecting thread: {str(exc)}"

    @tool
    def approve_comment(comment_id: str, score: float, reason: str) -> str:
        try:
            service.update_comment_review(
                comment_id=UUID(comment_id),
                status="approved",
                score=score,
                reviewed_at=datetime.now(UTC),
            )
            return f"Comment {comment_id} approved (score: {score}). {reason}"
        except Exception as exc:
            return f"Error approving comment: {str(exc)}"

    @tool
    def reject_comment(comment_id: str, score: float, reason: str) -> str:
        try:
            service.update_comment_review(
                comment_id=UUID(comment_id),
                status="rejected",
                score=score,
                reviewed_at=datetime.now(UTC),
            )
            service.delete_comment(UUID(comment_id))
            return f"Comment {comment_id} rejected (score: {score}) and deleted. {reason}"
        except Exception as exc:
            return f"Error rejecting comment: {str(exc)}"

    return [approve_thread, reject_thread, approve_comment, reject_comment]


def get_researcher_tools(service: AgentbookService) -> list:
    """Build researcher tools with service bound in closures."""

    @tool
    def research_problem(problem_id: str) -> str:
        """Get full context for a problem including all solutions and outcomes."""
        try:
            context = service.get_context(id=UUID(problem_id), include=["solutions", "similar"])
            return json.dumps(context, default=str)
        except Exception as exc:
            return f"Error getting problem context: {str(exc)}"

    @tool
    def propose_improvement(
        solution_id: str,
        improved_content: str,
        reasoning: str,
        steps: list[str] | None = None,
    ) -> str:
        """Submit an improved solution via the hill-climbing mechanism."""
        try:
            result = service.improve_solution(
                author_id=SYSTEM_AGENT_ID,
                solution_id=UUID(solution_id),
                improved_content=improved_content,
                improved_steps=steps,
                reasoning=reasoning,
                author_verified=True,
            )
            return f"Status: {result['status']}. Confidence: {result['previous_confidence']:.2f} -> {result['new_confidence']:.2f}"
        except Exception as exc:
            return f"Error proposing improvement: {str(exc)}"

    @tool
    def skip_improvement(problem_id: str, reason: str) -> str:
        """Skip improvement when no better solution is possible."""
        try:
            service.record_research_skip(
                problem_id=UUID(problem_id),
                researcher_id=SYSTEM_AGENT_ID,
                reasoning=reason,
            )
        except Exception as exc:
            logger.warning(f"Failed to record research skip for problem {problem_id}: {exc}")
        return f"Status: no_improvement. Reason: {reason}"

    return [research_problem, propose_improvement, skip_improvement]
