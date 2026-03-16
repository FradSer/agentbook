from __future__ import annotations

import logging
from uuid import UUID

from agent.src.config import settings

logger = logging.getLogger(__name__)


async def _run_agent(agent, prompt: str) -> str:
    import asyncio

    async_runner = getattr(agent, "arun", None)
    if callable(async_runner):
        response = await async_runner(prompt)
    else:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, agent.run, prompt)
    return str(response)


async def run_research_cycle(agent, service) -> dict:
    """One iteration of the autonomous research loop.

    1. Find research candidates (problems needing improvement)
    2. For each candidate, gather context + outcomes and ask AI to propose improvement
    3. Agent calls propose_improvement or skip_improvement tool directly
    4. Parse tool return string for "Status: improved" / "Status: no_improvement"
    """
    if not settings.agent_research_enabled:
        return {"skipped": True, "reason": "research disabled"}

    candidates = service.find_research_candidates(
        limit=settings.agent_research_batch_size,
        cooldown_hours=settings.agent_research_cooldown_hours,
    )
    if not candidates:
        logger.info("No research candidates found")
        return {"candidates": 0, "improved": 0, "no_improvement": 0}

    improved = 0
    no_improvement = 0

    for problem_dict in candidates:
        problem_id = problem_dict["problem_id"]
        try:
            context = service.get_context(id=problem_id, include=["solutions"])
        except Exception as exc:
            logger.warning(f"Failed to get context for problem {problem_id}: {exc}")
            continue

        solutions = context.get("solutions", [])
        if not solutions:
            logger.debug(f"Problem {problem_id} has no solutions to improve")
            continue

        # Sort by confidence descending so solutions[0] is the best (explicit, not implicit)
        solutions = sorted(solutions, key=lambda s: s.get("confidence", 0), reverse=True)

        # Fetch outcomes for each solution to give the agent real signal
        outcomes_by_solution: dict[str, list[dict]] = {}
        for sol in solutions:
            sol_id = str(sol["solution_id"])
            try:
                sol_context = service.get_context(id=UUID(sol_id), include=["outcomes"])
                outcomes_by_solution[sol_id] = sol_context.get("outcomes", [])
            except Exception:
                outcomes_by_solution[sol_id] = []

        prompt = _build_research_prompt(problem_dict, solutions, outcomes_by_solution)

        try:
            response_text = await _run_agent(agent, prompt)

            # Agent calls propose_improvement or skip_improvement tool directly.
            # Both tools return strings containing "Status: improved" or "Status: no_improvement".
            if "Status: improved" in response_text:
                improved += 1
                logger.info(f"Improved solution for problem {problem_id}")
                await _maybe_synthesize(service, UUID(str(problem_id)), agent)
            elif "Status: no_improvement" in response_text:
                no_improvement += 1
                logger.info(f"No improvement proposed for problem {problem_id}")
            else:
                logger.warning(
                    f"Agent returned no recognisable tool call for problem {problem_id}: "
                    f"{response_text[:200]!r}"
                )
                no_improvement += 1

        except Exception as exc:
            logger.error(f"Research cycle error for problem {problem_id}: {exc}")
            no_improvement += 1

    return {
        "candidates": len(candidates),
        "improved": improved,
        "no_improvement": no_improvement,
    }


async def _maybe_synthesize(service, problem_id: UUID, agent) -> None:
    """Trigger synthesis when enough solutions exist (≥10, or any with low confidence + outcomes)."""
    try:
        context = service.get_context(id=problem_id, include=["solutions"])
        solutions_data = context.get("solutions", [])
        active = [s for s in solutions_data if s.get("canonical_id") is None]

        needs_synthesis = len(active) >= 10 or any(
            s.get("confidence", 1.0) < 0.3 and s.get("outcome_count", 0) >= 10
            for s in active
        )
        if not needs_synthesis:
            return

        problem_data = context.get("data", {})
        synthesis_prompt = f"Problem: {problem_data.get('description', '')}\n\n"
        for i, s in enumerate(active[:10], 1):
            content_preview = s.get("content", "")[:500]
            synthesis_prompt += f"Solution {i}:\n{content_preview}\n\n"
        synthesis_prompt += "Please synthesize these solutions into one comprehensive canonical solution."

        try:
            synthesized_content = await _run_agent(agent, synthesis_prompt)
        except Exception as llm_exc:
            logger.warning(f"LLM synthesis failed for problem {problem_id}, skipping: {llm_exc}")
            return

        from agent.src.synthesis import SYSTEM_AGENT_ID
        result = service.synthesize_solutions(
            problem_id=problem_id,
            synthesized_content=synthesized_content,
            author_id=SYSTEM_AGENT_ID,
        )
        if result is not None:
            logger.info(
                f"Synthesized {result['synthesized_from']} solutions for problem {problem_id}"
            )
    except Exception as exc:
        logger.warning(f"Synthesis skipped for problem {problem_id}: {exc}")


def _build_research_prompt(
    problem: dict,
    solutions: list[dict],
    outcomes_by_solution: dict[str, list[dict]] | None = None,
) -> str:
    lines = [
        f"Problem: {problem['description']}",
        "",
    ]
    if problem.get("error_signature"):
        lines.append(f"Error signature: {problem['error_signature']}")
        lines.append("")

    best = solutions[0]
    best_id = str(best["solution_id"])
    lines.append(f"Current best solution (confidence: {best.get('confidence', 0):.2f}):")
    lines.append(best.get("content", ""))
    lines.append("")

    if outcomes_by_solution:
        outcomes = outcomes_by_solution.get(best_id, [])
        if outcomes:
            successes = sum(1 for o in outcomes if o.get("success"))
            failures = len(outcomes) - successes
            lines.append(f"Outcomes: {successes} success, {failures} failure(s)")
            failure_notes = [
                o.get("notes") for o in outcomes
                if not o.get("success") and o.get("notes")
            ]
            if failure_notes:
                lines.append("Failure notes:")
                for note in failure_notes[:3]:
                    lines.append(f"  - {note}")
            envs = [o.get("environment") for o in outcomes if o.get("environment")]
            if envs:
                lines.append(f"Environments tested: {envs[:3]}")
            lines.append("")

    if len(solutions) > 1:
        lines.append("Other solutions:")
        for sol in solutions[1:3]:
            lines.append(f"- (confidence: {sol.get('confidence', 0):.2f}) {sol.get('content', '')[:200]}")
        lines.append("")

    problem_id = problem["problem_id"]
    lines.append(
        f"Use propose_improvement(solution_id='{best_id}', ...) to submit a better solution, "
        f"or skip_improvement(problem_id='{problem_id}', ...) if no improvement is possible."
    )
    return "\n".join(lines)
