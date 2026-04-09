import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from agno.tools import tool

from agent.src.config import settings
from agent.src.synthesis import SYSTEM_AGENT_ID
from backend.application.service import AgentbookService


def _researcher_llm_model() -> str:
    return settings.agent_researcher_model_name or settings.agent_model_name


logger = logging.getLogger(__name__)


def get_reviewer_tools(service: AgentbookService) -> list:
    """Build reviewer tools with service bound in closures."""

    @tool
    def approve_content(content_id: str, reason: str) -> str:
        service.update_review(
            content_id=UUID(content_id),
            status="approved",
            score=1.0,
            reviewed_at=datetime.now(UTC),
        )
        return f"approved:{content_id}"

    @tool
    def reject_content(content_id: str, reason: str) -> str:
        service.update_review(
            content_id=UUID(content_id),
            status="rejected",
            score=0.0,
            reviewed_at=datetime.now(UTC),
        )
        service.delete_content(UUID(content_id))
        return f"rejected:{content_id}"

    return [approve_content, reject_content]


def get_researcher_tools(service: AgentbookService) -> list:
    """Build researcher tools with service bound in closures."""

    @tool
    def research_problem(problem_id: str) -> str:
        """Get full context for a problem including all solutions and outcomes."""
        try:
            context = service.inspect_resource(
                resource_id=UUID(problem_id), include=["solutions", "similar"]
            )
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
                solution_id=UUID(solution_id),
                improved_content=improved_content,
                improved_steps=steps,
                reasoning=reasoning,
                author_id=SYSTEM_AGENT_ID,
                llm_model=_researcher_llm_model(),
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
                llm_model=_researcher_llm_model(),
            )
        except Exception as exc:
            logger.warning(
                f"Failed to record research skip for problem {problem_id}: {exc}"
            )
        return f"Status: no_improvement. Reason: {reason}"

    return [research_problem, propose_improvement, skip_improvement]
