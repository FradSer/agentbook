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


async def _fetch_outcomes_by_solution(
    service, solutions: list[dict]
) -> dict[str, list[dict]]:
    """Fetch outcomes for each solution concurrently."""

    def _get(sol_id: str) -> list[dict]:
        try:
            ctx = service.inspect_resource(
                resource_id=UUID(sol_id), include=["outcomes"]
            )
            return ctx.get("outcomes", [])
        except Exception:
            return []

    sol_ids = [str(sol["solution_id"]) for sol in solutions]
    results = await asyncio.gather(
        *(asyncio.to_thread(_get, sol_id) for sol_id in sol_ids)
    )
    return dict(zip(sol_ids, results, strict=True))


async def run_research_cycle(agent, service, cooldown_hours: int | None = None) -> dict:
    """One iteration of the autonomous research loop.

    1. Find research candidates (problems needing improvement)
    2. For each candidate, gather context + outcomes and ask AI to propose improvement
    3. Agent calls propose_improvement or skip_improvement tool directly
    4. Parse tool return string for "Status: improved" / "Status: no_improvement"

    When ``agent_research_focus_mode`` is enabled, picks ONE candidate and
    iterates depth-first (up to ``agent_research_focus_max_iterations``) until
    stall or convergence, matching autoresearch's depth-first pattern.

    Args:
        agent: ResearcherAgent instance with propose_improvement / skip_improvement tools.
        service: AgentbookService instance.
        cooldown_hours: Override for agent_research_cooldown_hours setting (e.g. 0 in tests).
    """
    if not settings.agent_research_enabled:
        return {"skipped": True, "reason": "research disabled"}

    if settings.agent_research_focus_mode:
        return await _run_focused_research_cycle(agent, service, cooldown_hours)

    effective_cooldown = (
        settings.agent_research_cooldown_hours
        if cooldown_hours is None
        else cooldown_hours
    )
    candidates = service.find_research_candidates(
        limit=settings.agent_research_batch_size,
        cooldown_hours=effective_cooldown,
        max_confidence=settings.agent_research_max_confidence,
        stall_threshold=settings.agent_research_stall_threshold
        + 1,  # +1: radical exploration round before synthesis
        # The improve-only loop cannot act on a problem with no solution; without
        # this, zero-solution stubs (solution_count ASC) crowd the candidate window
        # and every cycle no-ops on them.
        min_solution_count=1,
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
                context = service.inspect_resource(
                    resource_id=problem_id, include=["solutions"]
                )
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

            outcomes_by_solution = await _fetch_outcomes_by_solution(service, solutions)

            failed_approaches, radical_mode = service.get_failed_approaches(
                UUID(str(problem_id)), settings.agent_research_stall_threshold
            )

            prompt = _build_research_prompt(
                problem_dict,
                solutions,
                outcomes_by_solution,
                failed_approaches=failed_approaches,
                radical_mode=radical_mode,
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
                    _maybe_trigger_synthesis(
                        service, problem_id, active_solutions, problem_dict
                    )
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


async def _run_focused_research_cycle(
    agent, service, cooldown_hours: int | None = None
) -> dict:
    """Depth-first research: pick 1 problem, iterate until stall or max iterations.

    Matches autoresearch's pattern of deep iteration on a single problem.
    """
    effective_cooldown = (
        settings.agent_research_cooldown_hours
        if cooldown_hours is None
        else cooldown_hours
    )
    candidates = service.find_research_candidates(
        limit=1,
        cooldown_hours=effective_cooldown,
        max_confidence=settings.agent_research_max_confidence,
        stall_threshold=settings.agent_research_stall_threshold + 1,
        min_solution_count=1,  # focus mode also only improves existing solutions
    )
    if not candidates:
        logger.info("No research candidates found (focus mode)")
        return {"candidates": 0, "improved": 0, "no_improvement": 0, "focus_mode": True}

    problem_dict = candidates[0]
    problem_id = problem_dict["problem_id"]
    improved = 0
    no_improvement = 0
    consecutive_no_improvement = 0
    max_iterations = settings.agent_research_focus_max_iterations

    logger.info(
        f"Focus mode: iterating on problem {problem_id} (max {max_iterations} rounds)"
    )

    with contextlib.suppress(Exception):
        service.set_research_status(UUID(str(problem_id)), True)

    try:
        for iteration in range(max_iterations):
            logger.info(
                f"Focus mode iteration {iteration + 1}/{max_iterations} "
                f"for problem {problem_id}"
            )

            result = await _research_single_problem(agent, service, problem_dict)

            if result == "improved":
                improved += 1
                consecutive_no_improvement = 0
                # Refresh problem dict for next iteration (confidence may have changed)
                try:
                    ctx = service.inspect_resource(resource_id=problem_id, include=[])
                    problem_dict = {
                        "problem_id": problem_id,
                        "description": ctx.get(
                            "description", problem_dict["description"]
                        ),
                        "error_signature": ctx.get(
                            "error_signature", problem_dict.get("error_signature")
                        ),
                        "best_confidence": ctx.get(
                            "best_confidence", problem_dict.get("best_confidence")
                        ),
                    }
                except Exception:
                    pass
            else:
                no_improvement += 1
                consecutive_no_improvement += 1

            # Stop if stalled (matches stall_threshold)
            if consecutive_no_improvement >= settings.agent_research_stall_threshold:
                logger.info(
                    f"Focus mode: stalled after {consecutive_no_improvement} "
                    f"consecutive no-improvement cycles on problem {problem_id}"
                )
                # Attempt synthesis
                try:
                    ctx = service.inspect_resource(
                        resource_id=problem_id, include=["solutions"]
                    )
                    active_solutions = [
                        s
                        for s in ctx.get("solutions", [])
                        if s.get("canonical_id") is None
                    ]
                    _maybe_trigger_synthesis(
                        service, problem_id, active_solutions, problem_dict
                    )
                except Exception as exc:
                    logger.warning(f"Focus mode synthesis attempt failed: {exc}")
                break

    finally:
        with contextlib.suppress(Exception):
            service.set_research_status(UUID(str(problem_id)), False)

    return {
        "candidates": 1,
        "improved": improved,
        "no_improvement": no_improvement,
        "focus_mode": True,
        "iterations": improved + no_improvement,
    }


async def _research_single_problem(agent, service, problem_dict: dict) -> str:
    """Run one research iteration on a single problem. Returns 'improved' or 'no_improvement'."""
    problem_id = problem_dict["problem_id"]

    try:
        context = service.inspect_resource(
            resource_id=problem_id, include=["solutions"]
        )
    except Exception as exc:
        logger.warning(f"Failed to get context for problem {problem_id}: {exc}")
        return "no_improvement"

    solutions = context.get("solutions", [])
    if not solutions:
        return "no_improvement"

    active_solutions = [s for s in solutions if s.get("canonical_id") is None]
    if not active_solutions:
        return "no_improvement"

    solutions = sorted(
        active_solutions, key=lambda s: s.get("confidence", 0), reverse=True
    )

    outcomes_by_solution = await _fetch_outcomes_by_solution(service, solutions)

    failed_approaches, radical_mode = service.get_failed_approaches(
        UUID(str(problem_id)), settings.agent_research_stall_threshold
    )

    prompt = _build_research_prompt(
        problem_dict,
        solutions,
        outcomes_by_solution,
        failed_approaches=failed_approaches,
        radical_mode=radical_mode,
    )

    try:
        response_text = await asyncio.wait_for(
            _run_agent(agent, prompt),
            timeout=settings.agent_research_per_candidate_timeout_seconds,
        )
        if "Status: improved" in response_text:
            return "improved"
        if "Status: no_improvement" in response_text:
            return "no_improvement"
        logger.warning(
            f"Agent returned no recognisable tool call for problem {problem_id}: "
            f"{response_text[:200]!r}"
        )
        with contextlib.suppress(Exception):
            service.record_research_skip(
                problem_id=UUID(str(problem_id)),
                researcher_id=SYSTEM_AGENT_ID,
                reasoning="Agent returned no recognisable tool call",
                status="no_solution_proposed",
                llm_model=_researcher_llm_model(),
            )
        return "no_improvement"
    except TimeoutError:
        logger.warning(f"Focus mode: problem {problem_id} timed out")
        with contextlib.suppress(Exception):
            service.record_research_skip(
                problem_id=UUID(str(problem_id)),
                researcher_id=SYSTEM_AGENT_ID,
                reasoning="Research candidate timed out",
                status="no_solution_proposed",
                llm_model=_researcher_llm_model(),
            )
        return "no_improvement"
    except Exception as exc:
        logger.error(f"Focus mode error for problem {problem_id}: {exc}")
        with contextlib.suppress(Exception):
            service.record_research_skip(
                problem_id=UUID(str(problem_id)),
                researcher_id=SYSTEM_AGENT_ID,
                reasoning=f"Research cycle error: {exc}",
                status="no_solution_proposed",
                llm_model=_researcher_llm_model(),
            )
        return "no_improvement"


def _synthesize_structured_knowledge(active_solutions, problem_dict):
    """Best-effort LLM distillation of the active solutions into canonical
    content plus transferable structured knowledge. Returns ``None`` on any
    failure (no key, model error, unparseable reply) so synthesis falls back to
    the mechanical union merge in the service.
    """
    if problem_dict is None:
        return None
    try:
        from agent.src.researcher_agent import build_synthesis_llm_fn
        from agent.src.synthesis import synthesize_structured_knowledge

        return synthesize_structured_knowledge(
            active_solutions, problem_dict, build_synthesis_llm_fn()
        )
    except Exception as exc:  # noqa: BLE001 -- distillation is strictly optional
        logger.warning(f"Structured synthesis distillation failed: {exc}")
        return None


def _maybe_trigger_synthesis(
    service, problem_id, active_solutions: list[dict], problem_dict: dict | None = None
) -> None:
    """Auto-trigger synthesis when research has stalled and enough solutions exist.

    When ``agent_research_post_synthesis_continue`` is enabled, records a
    ``synthesis_completed`` research cycle after synthesis so the stall counter
    resets and the problem re-enters the hill-climbing loop.
    """
    if len(active_solutions) < 3:
        return
    try:
        pid = UUID(str(problem_id))
        stalled = service.count_consecutive_no_improvement(pid)
        if stalled < settings.agent_research_stall_threshold + 1:
            return
        logger.info(
            f"Problem {problem_id}: {stalled} consecutive no-improvement cycles with "
            f"{len(active_solutions)} active solutions — triggering synthesis"
        )
        distilled = _synthesize_structured_knowledge(active_solutions, problem_dict)
        result = service.synthesize_solutions(
            problem_id=pid,
            author_id=SYSTEM_AGENT_ID,
            llm_model=settings.agent_model_name,
            synthesized_content=(distilled or {}).get("content"),
            synthesized_root_cause_pattern=(distilled or {}).get("root_cause_pattern"),
            synthesized_localization_cues=(distilled or {}).get("localization_cues"),
            synthesized_verification=(distilled or {}).get("verification"),
            synthesized_root_cause_class=(distilled or {}).get("root_cause_class"),
        )

        if result and settings.agent_research_post_synthesis_continue:
            from backend.domain.models import ResearchCycle

            service.record_research_cycle(
                ResearchCycle(
                    problem_id=pid,
                    researcher_id=SYSTEM_AGENT_ID,
                    proposed_solution_id=result.get("canonical_solution_id"),
                    previous_best_confidence=0.0,
                    new_confidence=result.get("confidence", 0.0),
                    status="synthesis_completed",
                    reasoning=f"Synthesized from {result.get('synthesized_from', 0)} solutions",
                    llm_model=settings.agent_model_name,
                )
            )
            logger.info(
                f"Problem {problem_id}: synthesis completed, stall counter reset "
                f"(post_synthesis_continue=True)"
            )
    except Exception as exc:
        logger.warning(f"Auto-synthesis failed for problem {problem_id}: {exc}")


def _build_research_prompt(
    problem: dict,
    solutions: list[dict],
    outcomes_by_solution: dict[str, list[dict]] | None = None,
    failed_approaches: list[str] | None = None,
    radical_mode: bool = False,
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
            "Your proposal will be evaluated on content quality heuristics. "
            "Focus on well-structured, concrete solutions with clear steps."
        )
        lines.append("")

    if failed_approaches:
        lines.append("## Past Failed Attempts (DO NOT repeat these)")
        for approach in failed_approaches[:5]:
            lines.append(f"  - {approach}")
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

    # Cross-solution environment priority: highlight the weakest environment
    if outcomes_by_solution:
        all_env_stats: dict[str, list[bool]] = {}
        for sol_outcomes in outcomes_by_solution.values():
            for o in sol_outcomes:
                env = o.get("environment")
                if env:
                    key = str(sorted(env.items()))
                    all_env_stats.setdefault(key, []).append(bool(o.get("success")))
        if len(all_env_stats) >= 2:
            weakest = min(all_env_stats.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))
            best_env = max(
                all_env_stats.items(), key=lambda kv: sum(kv[1]) / len(kv[1])
            )
            weakest_rate = sum(weakest[1]) / len(weakest[1])
            best_rate = sum(best_env[1]) / len(best_env[1])
            if weakest_rate < best_rate:
                lines.append(
                    f"PRIORITY: Fix environment {weakest[0]} "
                    f"(success rate: {weakest_rate:.0%} vs best: {best_rate:.0%})"
                )
                lines.append("")

    if radical_mode:
        lines.append("## RADICAL EXPLORATION MODE")
        lines.append("Previous incremental improvements have stalled.")
        lines.append("Try FUNDAMENTALLY different approaches:")
        lines.append("- Combine the best aspects of ALL existing solutions")
        lines.append("- Challenge the problem's assumptions")
        lines.append("- Consider a completely different solution strategy")
        lines.append("- Think harder: re-read the problem, try radical changes")
        lines.append("")

    problem_id = problem["problem_id"]
    lines.append(
        f"Use propose_improvement(solution_id='{best_id}', ...) to submit a better solution, "
        f"or skip_improvement(problem_id='{problem_id}', ...) if no improvement is possible."
    )
    return "\n".join(lines)
