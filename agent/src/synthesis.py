from __future__ import annotations

from uuid import UUID

from app.domain.models import Problem, Solution

SYSTEM_AGENT_ID = UUID("00000000-0000-0000-0000-000000000001")


def should_trigger_synthesis(
    solutions: list[Solution], similarity_matrix: dict
) -> bool:
    if len(solutions) >= 10:
        return True

    for s in solutions:
        if s.confidence < 0.3 and s.outcome_count >= 10:
            return True

    n = len(solutions)
    for i in range(n):
        cluster = [solutions[i]]
        for j in range(n):
            if i == j:
                continue
            sim = similarity_matrix.get(
                (solutions[i].solution_id, solutions[j].solution_id), 0.0
            )
            if sim > 0.85:
                all_similar = all(
                    similarity_matrix.get(
                        (m.solution_id, solutions[j].solution_id), 0.0
                    )
                    > 0.85
                    for m in cluster
                )
                if all_similar:
                    cluster.append(solutions[j])
        if len(cluster) >= 3:
            return True

    return False


def find_synthesis_candidates(
    problems: list[Problem],
    solutions_by_problem: dict,
    similarity_fn,
) -> list[list[Solution]]:
    result: list[list[Solution]] = []
    for problem in problems:
        sols = [
            s
            for s in solutions_by_problem.get(problem.problem_id, [])
            if s.canonical_id is None
        ]
        if len(sols) < 2:
            continue
        matrix: dict = {}
        for i, a in enumerate(sols):
            for j, b in enumerate(sols):
                if i != j:
                    matrix[(a.solution_id, b.solution_id)] = similarity_fn(a, b)
        if should_trigger_synthesis(sols, matrix):
            result.append(sols)
    return result


def synthesize_solutions(
    solutions: list[Solution], problem: Problem, llm_fn
) -> Solution:
    prompt = f"Problem: {problem.description}\n\n"
    for i, s in enumerate(solutions, 1):
        prompt += f"Solution {i}:\n{s.content}\n\n"
    prompt += "Please synthesize these solutions into one comprehensive canonical solution."

    synthesized_content = llm_fn(prompt)

    total_outcomes = sum(s.outcome_count for s in solutions)
    total_successes = sum(s.success_count for s in solutions)
    confidence = total_successes / total_outcomes if total_outcomes > 0 else 0.5

    return Solution(
        problem_id=problem.problem_id,
        author_id=SYSTEM_AGENT_ID,
        content=synthesized_content,
        author_verified=True,
        confidence=confidence,
        outcome_count=total_outcomes,
        success_count=total_successes,
        failure_count=sum(s.failure_count for s in solutions),
    )


def _mark_superseded(solutions: list[Solution], canonical_id: UUID) -> list[Solution]:
    for s in solutions:
        object.__setattr__(s, "canonical_id", canonical_id)
    return solutions
