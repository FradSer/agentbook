from __future__ import annotations

from uuid import UUID

from backend.domain.models import Outcome, Problem, Solution

SYSTEM_AGENT_ID = UUID("00000000-0000-0000-0000-000000000001")


def synthesize_solutions(
    solutions: list[Solution],
    problem: Problem,
    llm_fn,
    outcomes: list[Outcome] | None = None,
) -> Solution:
    prompt = f"Problem: {problem.description}\n\n"
    for i, s in enumerate(solutions, 1):
        prompt += f"Solution {i}:\n{s.content}\n\n"
    prompt += "Please synthesize these solutions into one comprehensive canonical solution."

    synthesized_content = llm_fn(prompt)

    total_outcomes = sum(s.outcome_count for s in solutions)
    total_successes = sum(s.success_count for s in solutions)

    if outcomes is not None:
        from backend.application.confidence import calculate_confidence
        confidence = calculate_confidence(outcomes, SYSTEM_AGENT_ID)
    else:
        confidence = total_successes / total_outcomes if total_outcomes > 0 else 0.5

    return Solution(
        problem_id=problem.problem_id,
        author_id=SYSTEM_AGENT_ID,
        content=synthesized_content,
        confidence=confidence,
        outcome_count=total_outcomes,
        success_count=total_successes,
        failure_count=sum(s.failure_count for s in solutions),
    )


def _mark_superseded(solutions: list[Solution], canonical_id: UUID) -> list[Solution]:
    for s in solutions:
        object.__setattr__(s, "canonical_id", canonical_id)
    return solutions
