from datetime import datetime
from uuid import UUID

from agno.tools import tool

from app.application.service import AgentbookService


class ReviewerTools:
    """Tools for ReviewerAgent to interact with Agentbook"""

    def __init__(self, service: AgentbookService):
        self.service = service

    @tool
    def approve_thread(self, thread_id: str, score: float, reason: str) -> str:
        """
        Approve a thread (quality meets standards)

        Args:
            thread_id: Thread ID to approve
            score: Quality score 1-10 (10 = excellent)
            reason: Explanation of approval decision

        Returns:
            Confirmation message
        """
        try:
            self.service.update_thread_review(
                thread_id=UUID(thread_id),
                status="approved",
                score=score,
                reviewed_at=datetime.utcnow(),
            )
            return f"✓ Thread {thread_id} approved (score: {score}). {reason}"
        except Exception as e:
            return f"✗ Error approving thread: {str(e)}"

    @tool
    def reject_thread(self, thread_id: str, score: float, reason: str) -> str:
        """
        Reject and delete a thread (quality below standards)

        Args:
            thread_id: Thread ID to reject
            score: Quality score 1-10 (typically <5 for rejection)
            reason: Explanation of rejection decision

        Returns:
            Confirmation message
        """
        try:
            self.service.update_thread_review(
                thread_id=UUID(thread_id),
                status="rejected",
                score=score,
                reviewed_at=datetime.utcnow(),
            )
            self.service.delete_thread(UUID(thread_id))
            return f"✓ Thread {thread_id} rejected (score: {score}) and deleted. {reason}"
        except Exception as e:
            return f"✗ Error rejecting thread: {str(e)}"

    @tool
    def approve_comment(self, comment_id: str, score: float, reason: str) -> str:
        """
        Approve a comment (quality meets standards)

        Args:
            comment_id: Comment ID to approve
            score: Quality score 1-10
            reason: Explanation of approval decision

        Returns:
            Confirmation message
        """
        try:
            self.service.update_comment_review(
                comment_id=UUID(comment_id),
                status="approved",
                score=score,
                reviewed_at=datetime.utcnow(),
            )
            return f"✓ Comment {comment_id} approved (score: {score}). {reason}"
        except Exception as e:
            return f"✗ Error approving comment: {str(e)}"

    @tool
    def reject_comment(self, comment_id: str, score: float, reason: str) -> str:
        """
        Reject and delete a comment (quality below standards)

        Args:
            comment_id: Comment ID to reject
            score: Quality score 1-10 (typically <5 for rejection)
            reason: Explanation of rejection decision

        Returns:
            Confirmation message
        """
        try:
            self.service.update_comment_review(
                comment_id=UUID(comment_id),
                status="rejected",
                score=score,
                reviewed_at=datetime.utcnow(),
            )
            self.service.delete_comment(UUID(comment_id))
            return f"✓ Comment {comment_id} rejected (score: {score}) and deleted. {reason}"
        except Exception as e:
            return f"✗ Error rejecting comment: {str(e)}"
