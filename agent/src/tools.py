from datetime import UTC, datetime
from uuid import UUID

from agno.tools import tool

from app.application.service import AgentbookService


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
            return f"✓ Thread {thread_id} approved (score: {score}). {reason}"
        except Exception as exc:
            return f"✗ Error approving thread: {str(exc)}"

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
                f"✓ Thread {thread_id} rejected (score: {score}) and deleted. {reason}"
            )
        except Exception as exc:
            return f"✗ Error rejecting thread: {str(exc)}"

    @tool
    def approve_comment(comment_id: str, score: float, reason: str) -> str:
        try:
            service.update_comment_review(
                comment_id=UUID(comment_id),
                status="approved",
                score=score,
                reviewed_at=datetime.now(UTC),
            )
            return f"✓ Comment {comment_id} approved (score: {score}). {reason}"
        except Exception as exc:
            return f"✗ Error approving comment: {str(exc)}"

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
            return f"✓ Comment {comment_id} rejected (score: {score}) and deleted. {reason}"
        except Exception as exc:
            return f"✗ Error rejecting comment: {str(exc)}"

    return [approve_thread, reject_thread, approve_comment, reject_comment]
