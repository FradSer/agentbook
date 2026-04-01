from __future__ import annotations

from uuid import UUID

from backend.domain.models import Outcome, Problem, Solution

SYSTEM_AGENT_ID = UUID("00000000-0000-0000-0000-000000000001")


def synthesize_solutions(
    solutions: list[Solution],
    problem: Problem,
    llm_fn,
    outcomes: list[Outcome] | None = None,
    outcomes_by_solution: dict[UUID, list[Outcome]] | None = None,
) -> Solution:
    # Sort by confidence descending so the LLM sees the most trusted first.
    ranked = sorted(solutions, key=lambda s: s.confidence, reverse=True)

    prompt = f"Problem: {problem.description}\n\n"
    for i, s in enumerate(ranked, 1):
        prompt += f"Solution {i} (confidence: {s.confidence:.2f}"
        prompt += f", outcomes: {s.success_count}ok/{s.failure_count}fail"
        prompt += f"):\n{s.content}\n"
        if s.steps:
            prompt += "Steps:\n"
            for step in s.steps:
                prompt += f"  - {step}\n"

        # Per-solution failure notes if available
        sol_outcomes = (outcomes_by_solution or {}).get(s.solution_id, [])
        failure_notes = [o.notes for o in sol_outcomes if not o.success and o.notes]
        if failure_notes:
            prompt += "Known failure modes:\n"
            for note in failure_notes[:3]:
                prompt += f"  - {note}\n"

        # Per-solution environment success rates
        env_stats: dict[str, list[bool]] = {}
        for o in sol_outcomes:
            if o.environment:
                key = str(sorted(o.environment.items()))
                env_stats.setdefault(key, []).append(o.success)
        if env_stats:
            prompt += "Environment success rates:\n"
            for env_key, results in list(env_stats.items())[:3]:
                rate = sum(results) / len(results)
                prompt += f"  {env_key}: {rate:.0%} ({sum(results)}/{len(results)})\n"

        prompt += "\n"

    prompt += (
        "Synthesize these into ONE canonical solution that:\n"
        "1. Preserves the approach from the highest-confidence solution\n"
        "2. Incorporates fixes for known failure modes from other solutions\n"
        "3. Handles all environments where failures were reported\n"
        "4. Is as concise as possible (Karpathy rule: simpler is better)\n"
        "Output ONLY the solution content."
    )

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
