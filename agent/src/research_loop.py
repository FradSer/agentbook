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
    2. For each candidate, gather context and ask AI to propose improvement
    3. If AI proposes improvement, call service.improve_solution()
    4. Record result
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

        best_solution = solutions[0]
        solution_id = best_solution["solution_id"]

        prompt = _build_research_prompt(problem_dict, solutions)

        try:
            response_text = await _run_agent(agent, prompt)
            parsed = _parse_agent_response(response_text)

            if parsed is None or not parsed.get("improved_content"):
                no_improvement += 1
                logger.info(f"No improvement proposed for problem {problem_id}")
                continue

            result = service.improve_solution(
                author_id=_get_system_agent_id(service),
                solution_id=UUID(str(solution_id)),
                improved_content=parsed["improved_content"],
                improved_steps=parsed.get("steps"),
                reasoning=parsed.get("reasoning", ""),
            )
            if result["status"] == "improved":
                improved += 1
                logger.info(
                    f"Improved solution for problem {problem_id}: "
                    f"{result['previous_confidence']:.2f} -> {result['new_confidence']:.2f}"
                )
                await _maybe_synthesize(service, UUID(str(problem_id)), agent)
            else:
                no_improvement += 1
                logger.info(f"Proposed solution did not improve confidence for problem {problem_id}")

        except Exception as exc:
            logger.error(f"Research cycle error for problem {problem_id}: {exc}")
            no_improvement += 1

    return {
        "candidates": len(candidates),
        "improved": improved,
        "no_improvement": no_improvement,
    }


async def _maybe_synthesize(service, problem_id: UUID, agent) -> None:
    """Trigger synthesis if the problem has enough solutions to warrant it."""
    from agent.src.synthesis import SYSTEM_AGENT_ID, find_synthesis_candidates, synthesize_solutions

    try:
        context = service.get_context(id=problem_id, include=["solutions"])
        solutions_data = context.get("solutions", [])
        if len(solutions_data) < 2:
            return

        # Rebuild domain Solution objects for synthesis check
        solutions = [service._solutions.get(s["solution_id"]) for s in solutions_data]
        solutions = [s for s in solutions if s is not None and s.canonical_id is None]

        problem = service._problems.get(problem_id)
        if problem is None or len(solutions) < 2:
            return

        # Simple similarity: always 0.0 (no embedding available in agent context)
        candidates = find_synthesis_candidates(
            [problem],
            {problem_id: solutions},
            lambda a, b: 0.0,
        )
        if not candidates:
            return

        # Build synthesis prompt and call LLM
        synthesis_prompt = f"Problem: {problem.description}\n\n"
        for i, s in enumerate(solutions, 1):
            synthesis_prompt += f"Solution {i}:\n{s.content}\n\n"
        synthesis_prompt += "Please synthesize these solutions into one comprehensive canonical solution."

        try:
            llm_result = await _run_agent(agent, synthesis_prompt)
        except Exception as llm_exc:
            logger.warning(f"LLM synthesis failed, falling back to concatenation: {llm_exc}")
            llm_result = "\n\n".join(s.content for s in solutions[:3])

        def llm_fn(prompt: str) -> str:
            return llm_result

        synthesized = synthesize_solutions(solutions, problem, llm_fn)
        service._solutions.add(synthesized)
        # Mark source solutions as superseded
        for s in solutions:
            object.__setattr__(s, "canonical_id", synthesized.solution_id)
            service._solutions.update(s)
        logger.info(f"Synthesized {len(solutions)} solutions for problem {problem_id}")
    except Exception as exc:
        logger.warning(f"Synthesis skipped for problem {problem_id}: {exc}")


def _build_research_prompt(problem: dict, solutions: list[dict]) -> str:
    lines = [
        f"Problem: {problem['description']}",
        "",
    ]
    if problem.get("error_signature"):
        lines.append(f"Error signature: {problem['error_signature']}")
        lines.append("")

    lines.append(f"Current best solution (confidence: {solutions[0].get('confidence', 0):.2f}):")
    lines.append(solutions[0].get("content", ""))
    lines.append("")

    if len(solutions) > 1:
        lines.append("Other solutions:")
        for sol in solutions[1:3]:
            lines.append(f"- (confidence: {sol.get('confidence', 0):.2f}) {sol.get('content', '')[:200]}")
        lines.append("")

    lines.extend([
        "Analyze the problem and existing solutions.",
        "If you can propose a genuinely better solution, respond with:",
        "IMPROVED_CONTENT: <your improved solution>",
        "STEPS: <step1> | <step2> | ...",
        "REASONING: <what you improved and why>",
        "",
        "If no improvement is possible, respond with:",
        "NO_IMPROVEMENT: <brief reason>",
    ])
    return "\n".join(lines)


def _parse_agent_response(text: str) -> dict | None:
    if "NO_IMPROVEMENT" in text:
        return None

    result: dict = {}
    for line in text.splitlines():
        if line.startswith("IMPROVED_CONTENT:"):
            result["improved_content"] = line[len("IMPROVED_CONTENT:"):].strip()
        elif line.startswith("STEPS:"):
            raw = line[len("STEPS:"):].strip()
            result["steps"] = [s.strip() for s in raw.split("|") if s.strip()]
        elif line.startswith("REASONING:"):
            result["reasoning"] = line[len("REASONING:"):].strip()

    return result if result.get("improved_content") else None


def _get_system_agent_id(service) -> UUID:
    from agent.src.synthesis import SYSTEM_AGENT_ID
    return SYSTEM_AGENT_ID
