"""The core agentic edit loop: linear history, single bash tool per turn."""

from __future__ import annotations

import time
from pathlib import Path

from harness.llm_openrouter import BudgetExhausted, LLMError, OpenRouterLLM
from harness.prompts import (
    SYSTEM_PROMPT,
    diagnose_edit_block,
    extract_command,
    extract_diff,
    extract_edits,
    is_done,
    looks_like_edit_intent,
    wants_apply_patch,
)
from harness.sandbox import (
    apply_search_replace,
    apply_unified_diff,
    git_checkpoint,
    git_reset_to,
    run_bash,
    run_verifications,
    search_not_found_hint,
)
from harness.transcript import Episode, Turn

_NO_BLOCK_HINT = (
    "No bash code block found in your reply. Respond with EXACTLY ONE ```bash "
    "block containing a single command, or ```bash\\necho AGENT_DONE\\n``` when "
    "the fix is complete."
)

# Malformed-edit feedback for the third dispatch branch. Used when the reply
# shows visible SEARCH/REPLACE intent (looks_like_edit_intent) but extract_edits
# could not isolate a pair. Tells the model the specific structural problem so
# it stops doom-looping the same truncated body. MUST NOT contain the
# "Respond with EXACTLY ONE ```bash" string from _NO_BLOCK_HINT -- the Feature 3
# scenario explicitly forbids that leaking into this branch.
_EDIT_MALFORMED_HINT = (
    "I could not apply your edit: {diag}. "
    "Re-emit ONE complete ```edit block with all five lines:\n"
    "  ```edit\n"
    "  path/to/file.py\n"
    "  <<<<<<< SEARCH\n"
    "  <lines to find>\n"
    "  =======\n"
    "  <lines to put in their place>\n"
    "  >>>>>>> REPLACE\n"
    "  ```\n"
    "Keep the body short (a single hunk) so the block fits in one reply."
)


# Consecutive failed apply attempts (parse-OK SEARCH/REPLACE or diff that does
# not locate) before aborting. Mirrors the 6-strike parse-failure cap: a weak
# model that re-emits the same non-matching block churns the whole budget on
# minutes-long generations otherwise (observed 15 identical fails on -15976).
_APPLY_FAIL_LIMIT = 5


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
    verification: dict | None = None,
) -> Episode:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task_prompt},
    ]
    episode = Episode()
    consecutive_parse_failures = 0
    consecutive_apply_failures = 0

    # good_loop: harness-owned apply->verify->retry. `verification.repros` is a
    # LIST of public repros (one per site for multi-site bugs); the harness runs
    # ALL after every edit, gates `done` on all-pass, and rolls back to the last
    # all-passing edit. Knowledge stays general -- only the execution CONDITION
    # changes. Multi-repro forces the model to cover all sites, not just one.
    vstate = {"passed": False, "pass_commit": None, "rejected_done": 0}
    repros = (verification or {}).get("repros") or []

    def _edit_feedback(ok: bool, ok_msg: str, fail_msg: str) -> str:
        """Default edit observation, augmented with a verification verdict when
        good_loop is active. Updates vstate (pass flag + rollback checkpoint)."""
        if not ok or not repros:
            return ok_msg if ok else fail_msg
        passed, out = run_verifications(repo, repros)
        episode.turns.append(
            Turn(
                turn=turn,
                command="<verify>",
                stdout_tail=out,
                stderr_tail="",
                returncode=0 if passed else 1,
                latency_ms=0,
            )
        )
        vstate["passed"] = passed
        if passed:
            vstate["pass_commit"] = (
                git_checkpoint(repo, "loop-pass") or vstate["pass_commit"]
            )
            return (
                f"edit applied and ALL {len(repros)} verification repros now PASS:\n"
                f"{out}\nIf the fix is complete, reply ```bash\\necho AGENT_DONE\\n```."
            )
        return (
            f"edit applied but the verification suite ({len(repros)} repros) is "
            f"not all passing:\n{out}\nA FAIL above means that site/case is still "
            "broken -- inspect it and extend the fix. Do not finish yet."
        )

    if repros:
        passed, out = run_verifications(repo, repros)
        vstate["passed"] = passed
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Before you start, here is the current state of the "
                    f"verification suite ({len(repros)} independent repros, all "
                    f"should fail until the fix is complete):\n{out}\nFix the bug "
                    "so ALL repros pass, then finish. A FAIL means that site/case "
                    "is still broken."
                ),
            }
        )

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

        # A ```edit block (SEARCH/REPLACE) is applied whitespace-tolerantly --
        # the most reliable edit path for weak models, which the good_synth arm
        # leans on since it must synthesize the edit (no patch to relay).
        edits = extract_edits(text)
        if edits:
            consecutive_parse_failures = 0
            t0 = time.time()
            ok, msg = apply_search_replace(repo, edits)
            episode.turns.append(
                Turn(
                    turn=turn,
                    command="<apply edit>",
                    stdout_tail=msg,
                    stderr_tail="",
                    returncode=0 if ok else 1,
                    latency_ms=int((time.time() - t0) * 1000),
                )
            )
            # On a non-match, echo the ACTUAL nearby file lines so the model
            # copies real text instead of re-emitting the same wrong SEARCH
            # (observed failed-apply doom-loop: 10+ identical non-matching blocks).
            fail_hint = (
                search_not_found_hint(repo, edits)
                if not ok and "not found" in msg
                else ""
            ) or (
                "Re-copy the exact SEARCH lines from the file (or use a "
                "```diff / direct edit)."
            )
            obs = _edit_feedback(
                ok,
                f"edit {msg}. Verify, then run a quick check or `echo AGENT_DONE`.",
                f"edit did NOT apply: {msg}. {fail_hint}",
            )
            messages.append({"role": "user", "content": obs})
            consecutive_apply_failures = 0 if ok else consecutive_apply_failures + 1
            if consecutive_apply_failures >= _APPLY_FAIL_LIMIT:
                episode.stop_reason = "apply_failures"
                episode.turns_used = turn
                break
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
            obs = _edit_feedback(
                ok,
                f"diff applied: {msg}. Verify, then run a quick check or "
                "`echo AGENT_DONE`.",
                f"diff did NOT apply: {msg}. Fix the diff context and retry, or edit "
                "directly.",
            )
            messages.append({"role": "user", "content": obs})
            consecutive_apply_failures = 0 if ok else consecutive_apply_failures + 1
            if consecutive_apply_failures >= _APPLY_FAIL_LIMIT:
                episode.stop_reason = "apply_failures"
                episode.turns_used = turn
                break
            continue

        # Edit-intent recovery: a SEARCH/REPLACE attempt that parsed to no
        # edits. Tell the model the specific structural problem, not the
        # generic "emit bash" hint -- otherwise the model doom-loops the same
        # truncated block (observed 4 identical turns in
        # good_multi_loop__sympy-15976__gemma4_e4b__s0). consecutive_parse_failures
        # still increments so the 6-strike abort fires; the doom-loop breaks
        # because the feedback CONTENT changes, not because the cap shrinks.
        if looks_like_edit_intent(text):
            consecutive_parse_failures += 1
            diag = diagnose_edit_block(text)
            episode.notes.append(
                f"turn {turn} unparseable-edit ({diag}): {(text or '').strip()[:300]}"
            )
            messages.append(
                {"role": "user", "content": _EDIT_MALFORMED_HINT.format(diag=diag)}
            )
            if consecutive_parse_failures >= 6:
                episode.stop_reason = "parse_failures"
                episode.turns_used = turn
                break
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
            # done-gate: in good_loop, refuse to finish while the verification
            # check still fails (up to 3 nudges), so the budget is spent retrying
            # rather than declaring a broken fix complete.
            if repros and not vstate["passed"] and vstate["rejected_done"] < 3:
                vstate["rejected_done"] += 1
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Not done yet: the verification check is still failing. "
                            "Re-read the failing site and refine the edit, then re-run "
                            "the check. Do not reply AGENT_DONE until it passes."
                        ),
                    }
                )
                continue
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

    # rollback: if good_loop ends in a failing state but a prior edit passed the
    # check, restore that last-passing tree so the model's best attempt is graded.
    if repros and not vstate["passed"] and vstate["pass_commit"]:
        git_reset_to(repo, vstate["pass_commit"])
        episode.notes.append(
            f"rolled back to passing checkpoint {vstate['pass_commit']}"
        )
    episode.verification_passed = vstate["passed"] if repros else None

    if not episode.turns_used:
        episode.turns_used = len(episode.turns)
    return episode
