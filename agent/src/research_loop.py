from __future__ import annotations

import asyncio
import contextlib
import logging
from uuid import UUID

from agent.src.config import settings
from agent.src.synthesis import SYSTEM_AGENT_ID

logger = logging.getLogger(__name__)


def _researcher_llm_model() -> str:
    return settings.agent_researcher_model_name or settings.agent_model_name


async def _run_agent(agent, prompt: str) -> str:
    async_runner = getattr(agent, "arun", None)
    if callable(async_runner):
        response = await async_runner(prompt)
    else:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, agent.run, prompt)
    return str(response)


async def run_research_cycle(agent, service, cooldown_hours: int | None = None) -> dict:
    """One iteration of the autonomous research loop.

    1. Find research candidates (problems needing improvement)
    2. For each candidate, gather context + outcomes and ask AI to propose improvement
    3. Agent calls propose_improvement or skip_improvement tool directly
    4. Parse tool return string for "Status: improved" / "Status: no_improvement"

    Args:
        agent: ResearcherAgent instance with propose_improvement / skip_improvement tools.
        service: AgentbookService instance.
        cooldown_hours: Override for agent_research_cooldown_hours setting (e.g. 0 in tests).
    """
    if not settings.agent_research_enabled:
        return {"skipped": True, "reason": "research disabled"}

    effective_cooldown = (
        settings.agent_research_cooldown_hours
        if cooldown_hours is None
        else cooldown_hours
    )
    candidates = service.find_research_candidates(
        limit=settings.agent_research_batch_size,
        cooldown_hours=effective_cooldown,
        max_confidence=settings.agent_research_max_confidence,
        stall_threshold=settings.agent_research_stall_threshold,
    )
    if not candidates:
        logger.info("No research candidates found")
        return {"candidates": 0, "improved": 0, "no_improvement": 0}

    improved = 0
    no_improvement = 0

    for problem_dict in candidates:
        problem_id = problem_dict["problem_id"]
        with contextlib.suppress(Exception):
            service.set_research_status(UUID(str(problem_id)), True)
        try:
            try:
                context = service.get_context(id=problem_id, include=["solutions"])
            except Exception as exc:
                logger.warning(f"Failed to get context for problem {problem_id}: {exc}")
                continue

            solutions = context.get("solutions", [])
            if not solutions:
                logger.debug(f"Problem {problem_id} has no solutions to improve")
                continue

            # Filter superseded solutions (canonical_id is not None means superseded or synthesized)
            active_solutions = [s for s in solutions if s.get("canonical_id") is None]
            if not active_solutions:
                logger.debug(
                    f"Problem {problem_id} has no active (non-superseded) solutions"
                )
                continue
            # Sort by confidence descending so solutions[0] is the best (explicit, not implicit)
            solutions = sorted(
                active_solutions, key=lambda s: s.get("confidence", 0), reverse=True
            )

            # Fetch outcomes for each solution to give the agent real signal
            outcomes_by_solution: dict[str, list[dict]] = {}
            for sol in solutions:
                sol_id = str(sol["solution_id"])
                try:
                    sol_context = service.get_context(
                        id=UUID(sol_id), include=["outcomes"]
                    )
                    outcomes_by_solution[sol_id] = sol_context.get("outcomes", [])
                except Exception:
                    outcomes_by_solution[sol_id] = []

            prompt = _build_research_prompt(
                problem_dict, solutions, outcomes_by_solution
            )

            try:
                response_text = await asyncio.wait_for(
                    _run_agent(agent, prompt),
                    timeout=settings.agent_research_per_candidate_timeout_seconds,
                )

                # Agent calls propose_improvement or skip_improvement tool directly.
                # Both tools return strings containing "Status: improved" or "Status: no_improvement".
                if "Status: improved" in response_text:
                    improved += 1
                    logger.info(f"Improved solution for problem {problem_id}")
                elif "Status: no_improvement" in response_text:
                    no_improvement += 1
                    logger.info(f"No improvement proposed for problem {problem_id}")
                    _maybe_trigger_synthesis(service, problem_id, active_solutions)
                else:
                    logger.warning(
                        f"Agent returned no recognisable tool call for problem {problem_id}: "
                        f"{response_text[:200]!r}"
                    )
                    no_improvement += 1
                    with contextlib.suppress(Exception):
                        service.record_research_skip(
                            problem_id=UUID(str(problem_id)),
                            researcher_id=SYSTEM_AGENT_ID,
                            reasoning="Agent returned no recognisable tool call",
                            status="no_solution_proposed",
                            llm_model=_researcher_llm_model(),
                        )

            except TimeoutError:
                logger.warning(
                    f"Research candidate {problem_id} timed out after "
                    f"{settings.agent_research_per_candidate_timeout_seconds}s"
                )
                no_improvement += 1
                with contextlib.suppress(Exception):
                    service.record_research_skip(
                        problem_id=UUID(str(problem_id)),
                        researcher_id=SYSTEM_AGENT_ID,
                        reasoning="Research candidate timed out",
                        status="no_solution_proposed",
                        llm_model=_researcher_llm_model(),
                    )
            except Exception as exc:
                logger.error(f"Research cycle error for problem {problem_id}: {exc}")
                no_improvement += 1
                with contextlib.suppress(Exception):
                    service.record_research_skip(
                        problem_id=UUID(str(problem_id)),
                        researcher_id=SYSTEM_AGENT_ID,
                        reasoning=f"Research cycle error: {exc}",
                        status="no_solution_proposed",
                        llm_model=_researcher_llm_model(),
                    )
        finally:
            with contextlib.suppress(Exception):
                service.set_research_status(UUID(str(problem_id)), False)

    return {
        "candidates": len(candidates),
        "improved": improved,
        "no_improvement": no_improvement,
    }


def _maybe_trigger_synthesis(service, problem_id, active_solutions: list[dict]) -> None:
    """Auto-trigger synthesis when research has stalled and enough solutions exist."""
    if len(active_solutions) < 3:
        return
    try:
        from uuid import UUID as _UUID

        if service._research_cycles is None:
            return
        stalled = service._research_cycles.consecutive_no_improvement(
            _UUID(str(problem_id))
        )
        if stalled < settings.agent_research_stall_threshold:
            return
        logger.info(
            f"Problem {problem_id}: {stalled} consecutive no-improvement cycles with "
            f"{len(active_solutions)} active solutions — triggering synthesis"
        )
        service.synthesize_solutions(
            problem_id=_UUID(str(problem_id)),
            author_id=SYSTEM_AGENT_ID,
            llm_model=settings.agent_model_name,
        )
    except Exception as exc:
        logger.warning(f"Auto-synthesis failed for problem {problem_id}: {exc}")


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
    lines.append(
        f"Current best solution (confidence: {best.get('confidence', 0):.2f}):"
    )
    lines.append(best.get("content", ""))
    lines.append("")

    total_outcomes = (
        sum(len(v) for v in outcomes_by_solution.values())
        if outcomes_by_solution
        else 0
    )

    if outcomes_by_solution:
        outcomes = outcomes_by_solution.get(best_id, [])
        if outcomes:
            successes = sum(1 for o in outcomes if o.get("success"))
            failures = len(outcomes) - successes
            lines.append(f"Outcomes: {successes} success, {failures} failure(s)")
            failure_notes = [
                o.get("notes")
                for o in outcomes
                if not o.get("success") and o.get("notes")
            ]
            if failure_notes:
                lines.append("Failure notes:")
                for note in failure_notes[:3]:
                    lines.append(f"  - {note}")
            # Per-environment success rates
            env_stats: dict[str, list[bool]] = {}
            for o in outcomes:
                env = o.get("environment")
                if env:
                    key = str(sorted(env.items()))
                    env_stats.setdefault(key, []).append(bool(o.get("success")))
            if env_stats:
                lines.append("Per-environment success rates:")
                for env_key, results in list(env_stats.items())[:4]:
                    rate = sum(results) / len(results)
                    lines.append(
                        f"  {env_key}: {rate:.0%} ({sum(results)}/{len(results)})"
                    )
            lines.append("")

    if total_outcomes == 0:
        lines.append(
            "NOTE: No outcome data yet (cold-start). "
            "Your proposal will be evaluated on baseline confidence only. "
            "Focus on correctness and clarity."
        )
        lines.append("")

    if len(solutions) > 1:
        lines.append("Other solutions (with failure patterns):")
        for sol in solutions[1:3]:
            sol_id = str(sol["solution_id"])
            sol_outcomes = (
                outcomes_by_solution.get(sol_id, []) if outcomes_by_solution else []
            )
            sol_failures = [
                o.get("notes")
                for o in sol_outcomes
                if not o.get("success") and o.get("notes")
            ]
            sol_line = f"- (confidence: {sol.get('confidence', 0):.2f}) {sol.get('content', '')[:150]}"
            if sol_failures:
                sol_line += f" | Failures: {'; '.join(sol_failures[:2])}"
            lines.append(sol_line)
        lines.append("")

    # Cross-solution failure pattern summary
    all_failure_notes = [
        o.get("notes")
        for outcomes in (outcomes_by_solution or {}).values()
        for o in outcomes
        if not o.get("success") and o.get("notes")
    ]
    if len(all_failure_notes) >= 2:
        lines.append("Common failure patterns across all solutions:")
        for note in all_failure_notes[:4]:
            lines.append(f"  - {note}")
        lines.append("")

    problem_id = problem["problem_id"]
    lines.append(
        f"Use propose_improvement(solution_id='{best_id}', ...) to submit a better solution, "
        f"or skip_improvement(problem_id='{problem_id}', ...) if no improvement is possible."
    )
    return "\n".join(lines)
