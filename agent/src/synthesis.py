from __future__ import annotations

import json
import re
from uuid import UUID

from backend.domain.models import Outcome, Problem, Solution

SYSTEM_AGENT_ID = UUID("00000000-0000-0000-0000-000000000001")

_JSON_FENCE_RE = re.compile(r"```json\s*\n(.*?)```", re.DOTALL)

_STRUCTURED_SYNTH_PROMPT = """You are a knowledge-synthesis agent for a shared \
debug-knowledge commons used by AI coding agents. Several agents solved the SAME problem \
below and left prose notes. Merge them into ONE canonical solution AND distil \
transferable, weak-model-actionable knowledge that lets a much weaker model \
re-derive and land the fix itself -- not copy a patch.

{sources}
Return ONLY a JSON object inside a single ```json fenced block with EXACTLY \
these fields:

- "content": the canonical solution prose. Preserve the highest-confidence \
approach, fold in fixes for failure modes the other notes mention, stay concise \
(Karpathy rule: simpler is better).
- "root_cause_class": a short kebab-case slug naming the ABSTRACT failure class \
so a sibling bug with different surface text matches it (e.g. \
"identity-element-fallback", "narrow-type-guard", "missing-dispatch-entry"). \
Pick the most general slug that still discriminates.
- "root_cause_pattern": the failure MODE as a reusable pattern plus the fix \
DIRECTION at a conceptual level, named so a sibling bug would match it. No \
line-by-line patch.
- "localization_cues": a list of 2-5 short strings telling where to look \
(module/file, class, function, code construct). Symbols are fine; verbatim new \
source lines are not.
- "verification": a list of 1-3 objects, each {{"command": <shell or python -c \
one-liner the engineer can run>, "expected": <expected vs buggy outcome>}}. \
Self-contained from the bug report -- never a hidden grading test.

Hard rules: output ONLY the fenced JSON object; no ```diff blocks, no \
multi-line code-to-paste-in."""


def _sol_attr(sol: object, key: str, default: object = None) -> object:
    if isinstance(sol, dict):
        return sol.get(key, default)
    return getattr(sol, key, default)


def _build_structured_synthesis_prompt(solutions: list, problem: object) -> str:
    description = _sol_attr(problem, "description", "") or ""
    blocks = f"Problem: {description}\n\n"
    for i, s in enumerate(solutions, 1):
        blocks += f"Solution {i}:\n{_sol_attr(s, 'content', '') or ''}\n"
        steps = _sol_attr(s, "steps") or []
        if steps:
            blocks += "Steps:\n" + "".join(f"  - {step}\n" for step in steps)
        blocks += "\n"
    return _STRUCTURED_SYNTH_PROMPT.format(sources=blocks)


def _extract_json_object(text: str) -> dict:
    """Pull the JSON object from the reply (fenced first, then first {...})."""
    match = _JSON_FENCE_RE.search(text or "")
    blob = match.group(1) if match else None
    if blob is None:
        start, end = (text or "").find("{"), (text or "").rfind("}")
        if start == -1 or end == -1:
            raise ValueError("no JSON object in reply")
        blob = text[start : end + 1]
    return json.loads(blob)


def synthesize_structured_knowledge(
    solutions: list, problem: object, llm_fn
) -> dict | None:
    """Distil active solutions into canonical content plus transferable
    structured knowledge (root_cause_pattern / localization_cues / verification).

    Returns ``None`` when the reply cannot be parsed or carries no content, so
    the caller falls back to the union merged from the source solutions.
    """
    prompt = _build_structured_synthesis_prompt(solutions, problem)
    try:
        obj = _extract_json_object(str(llm_fn(prompt)))
    except (ValueError, json.JSONDecodeError):
        return None

    content = str(obj.get("content", "")).strip()
    if not content:
        return None

    cues = obj.get("localization_cues") or []
    if isinstance(cues, str):
        cues = [cues]
    cues = [str(c).strip() for c in cues if str(c).strip()][:5]

    verification = obj.get("verification") or []
    if isinstance(verification, dict):
        verification = [verification]
    verification = [v for v in verification if isinstance(v, dict)][:3]

    root_cause = str(obj.get("root_cause_pattern", "")).strip() or None
    root_cause_class = _slugify(str(obj.get("root_cause_class", "")).strip()) or None

    return {
        "content": content,
        "root_cause_class": root_cause_class,
        "root_cause_pattern": root_cause,
        "localization_cues": cues,
        "verification": verification,
    }


def _slugify(text: str) -> str:
    """Normalise a class label to a kebab-case slug usable in a tag."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


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
