"""The core agentic edit loop: linear history, single bash tool per turn."""

from __future__ import annotations

import time
from pathlib import Path

from harness.llm_openrouter import BudgetExhausted, LLMError, OpenRouterLLM
from harness.prompts import (
    SYSTEM_PROMPT,
    extract_command,
    extract_diff,
    is_done,
    wants_apply_patch,
)
from harness.sandbox import apply_unified_diff, run_bash
from harness.transcript import Episode, Turn

_NO_BLOCK_HINT = (
    "No bash code block found in your reply. Respond with EXACTLY ONE ```bash "
    "block containing a single command, or ```bash\\necho AGENT_DONE\\n``` when "
    "the fix is complete."
)


def _observation(stdout: str, stderr: str, rc: int) -> str:
    parts = [f"exit code: {rc}"]
    if stdout.strip():
        parts.append(f"stdout:\n{stdout}")
    if stderr.strip():
        parts.append(f"stderr:\n{stderr}")
    if not stdout.strip() and not stderr.strip():
        parts.append("(no output)")
    return "\n".join(parts)


def run_episode(
    repo: Path,
    task_prompt: str,
    llm: OpenRouterLLM,
    model: str,
    *,
    step_budget: int = 40,
    temperature: float = 0.7,
    seed: int = 0,
    bash_timeout: int = 120,
    apply_patch: str | None = None,
) -> Episode:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task_prompt},
    ]
    episode = Episode()
    consecutive_parse_failures = 0

    for turn in range(1, step_budget + 1):
        try:
            text = llm.chat(model, messages, temperature=temperature, seed=seed)
        except BudgetExhausted:
            episode.stop_reason = "llm_error"
            episode.error = "day budget exhausted"
            break
        except LLMError as exc:
            episode.stop_reason = "llm_error"
            episode.error = str(exc)[:300]
            break

        messages.append({"role": "assistant", "content": text})

        # APPLY_PATCH: the good_apply "copy-the-answer" action -- the harness
        # applies the recalled verified patch so the weak model needn't reproduce
        # a diff it cannot wield. Checked before bash so a stray `git apply` in
        # the same reply doesn't pre-empt it.
        if apply_patch and wants_apply_patch(text):
            consecutive_parse_failures = 0
            t0 = time.time()
            ok, msg = apply_unified_diff(repo, apply_patch)
            episode.turns.append(
                Turn(
                    turn=turn,
                    command="<APPLY_PATCH>",
                    stdout_tail=msg,
                    stderr_tail="",
                    returncode=0 if ok else 1,
                    latency_ms=int((time.time() - t0) * 1000),
                )
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"patch applied: {msg}. Now verify briefly, then `echo "
                        "AGENT_DONE`."
                        if ok
                        else f"APPLY_PATCH failed: {msg}. Edit directly instead."
                    ),
                }
            )
            continue

        # A ```diff block is applied by the harness (git apply) -- the reliable
        # edit path for weak models that cannot wield sed/heredoc.
        diff = extract_diff(text)
        if diff is not None:
            consecutive_parse_failures = 0
            t0 = time.time()
            ok, msg = apply_unified_diff(repo, diff)
            episode.turns.append(
                Turn(
                    turn=turn,
                    command="<apply diff>",
                    stdout_tail=msg,
                    stderr_tail="",
                    returncode=0 if ok else 1,
                    latency_ms=int((time.time() - t0) * 1000),
                )
            )
            obs = (
                f"diff applied: {msg}. Verify, then run a quick check or "
                "`echo AGENT_DONE`."
                if ok
                else f"diff did NOT apply: {msg}. Fix the diff context and retry, "
                "or edit directly."
            )
            messages.append({"role": "user", "content": obs})
            continue

        command = extract_command(text)

        if command is None:
            consecutive_parse_failures += 1
            episode.notes.append(f"turn {turn} no-block: {(text or '').strip()[:300]}")
            messages.append({"role": "user", "content": _NO_BLOCK_HINT})
            if consecutive_parse_failures >= 6:
                episode.stop_reason = "parse_failures"
                episode.turns_used = turn
                break
            continue
        consecutive_parse_failures = 0

        if is_done(command):
            episode.stop_reason = "done"
            episode.turns_used = turn
            break

        t0 = time.time()
        stdout, stderr, rc = run_bash(repo, command, timeout=bash_timeout)
        latency = int((time.time() - t0) * 1000)
        episode.turns.append(
            Turn(
                turn=turn,
                command=command[:2000],
                stdout_tail=stdout,
                stderr_tail=stderr,
                returncode=rc,
                latency_ms=latency,
            )
        )
        messages.append({"role": "user", "content": _observation(stdout, stderr, rc)})
    else:
        episode.stop_reason = "budget"
        episode.turns_used = step_budget

    if not episode.turns_used:
        episode.turns_used = len(episode.turns)
    return episode
