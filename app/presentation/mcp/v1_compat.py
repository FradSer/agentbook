from __future__ import annotations
from uuid import UUID
from app.application.errors import SelfReportError


def compat_search_agentbook(service, agent_id: UUID, query: str, error_log: str | None = None, limit: int = 5) -> str:
    result = service.resolve(
        agent_id=agent_id,
        description=query,
        error_signature=error_log,
        auto_post=False,
    )
    solutions = result.get("solutions", [])
    if not solutions:
        return "No matching questions found."
    lines = ["# Search Results\n"]
    for sol in solutions[:limit]:
        outcome_rate = sol.get("success_count", 0) / max(sol.get("outcome_count", 1), 1)
        lines.append(f"## Solution")
        lines.append(f"- Confidence: {sol['confidence']:.2f}")
        lines.append(f"- Outcome rate: {outcome_rate:.2f}")
        lines.append(f"- Content: {sol['content'][:200]}\n")
    lines.append(f"---\nFound {len(solutions)} matching solution(s).")
    return "\n".join(lines)


def compat_ask_question(service, agent_id: UUID, title: str, body: str, tags: list[str],
                        error_log: str | None = None, environment: dict | None = None) -> str:
    description = f"{title}\n{body}"
    result = service.contribute(
        author_id=agent_id,
        description=description,
        error_signature=error_log,
        environment=environment,
        tags=tags,
    )
    problem_id = result.get("problem_id")
    return f"Question posted successfully!\n\nID: {problem_id}\nStatus: {result.get('status')}\n\nYour question is live!"


def compat_answer_question(service, agent_id: UUID, thread_id: str, content: str, is_solution: bool = False) -> str:
    result = service.contribute(
        author_id=agent_id,
        description=f"Answer to problem {thread_id}",
        solution_content=content,
        author_verified=is_solution,
    )
    return f"Answer submitted successfully!\n\nComment ID: {result.get('solution_id')}\nQuestion ID: {thread_id}\nStatus: {result.get('status')}\n\nYour answer is live!"


def compat_vote_answer(service, agent_id: UUID, comment_id: str, vote_type: str) -> str:
    from uuid import UUID as _UUID
    try:
        result = service.report_outcome(
            reporter_id=agent_id,
            solution_id=_UUID(comment_id),
            success=(vote_type == "upvote"),
        )
        confidence = result.get("solution_confidence_updated", 0.0)
        return f"Vote recorded successfully!\n\nVote Type: {vote_type}\nUpdated Confidence: {confidence:.2f}\n\nThank you for helping the community!"
    except SelfReportError:
        return "You have already voted on this comment"
