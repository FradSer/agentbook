#!/usr/bin/env python
"""Extract a machine-runnable check from each synth_cache entry's prose
`verification_method`, so the harness can OWN an apply->verify->retry loop
(the good_loop paradigm) instead of trusting the model to self-judge.

For each entry we add three fields (knowledge fields are left untouched, so the
good_synth arm stays valid):

    verification_command   -- one shell command runnable in the repo root that
                              exercises the bug (typically `python -c "..."`).
    verification_expected  -- a substring present in the command's output ONLY
                              after a correct fix (the PASS signal).
    verification_buggy     -- a substring present while the bug is unfixed
                              (sanity: the check must discriminate).

If a clean substring check is not feasible, Opus returns null for the fields and
good_loop falls back to plain good_synth (no auto-verify) for that task.

Usage:
  uv run python -m memory.extract_verification                 # all, skip done
  uv run python -m memory.extract_verification --redo --only sympy__sympy-15017
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from benchmark.paths import ORACLE  # noqa: E402

from memory.to_memory_entry import gold_added_lines, scrub_leak  # noqa: E402

CLAUDE_BIN = Path(os.path.expanduser("~/.local/bin/claude"))
SYNTH_CACHE = ORACLE / "synth_cache.json"

_PROVIDER_ENV = (
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
)

EXTRACT_PROMPT = """Convert this bug-fix verification note into MULTIPLE \
independent runnable repros, so a harness loop can require ALL to pass and \
detect multi-site fixes (a single repro often under-specifies when the bug \
spans several constructors / classes / branches).

Verification note: {verification_method}
Root-cause pattern: {root_cause_pattern}
Localization cues (each line may indicate a DIFFERENT site the fix must cover):
{cues}

Output a single JSON object inside one ```json fenced block with:
- "verifications": a LIST of 1-5 repro entries. Each entry has:
    - "label"   : one-line description of which site/case this exercises.
    - "command" : ONE shell command (usually `python -c "..."`) runnable at \
the repo root. No shell pipelines, no &&; a single command.
    - "expected": a substring OR a list of alternative substrings; PASS \
requires ANY one to appear in stdout+stderr after the fix. Keep literal and \
tight (e.g. "1 1", ["True","true"], "oo -oo").
    - "buggy"   : a substring that must be ABSENT after the fix (e.g. an \
exception name, a wrong value). Use null if there's no clean negative marker.

Rules:
- If the root cause spans MULTIPLE distinct sites (e.g. dense + sparse + \
mutable + immutable constructors, or print path A + print path B), produce ONE \
repro PER site so each is independently exercised. The list's length should \
match the number of distinct sites the fix must touch.
- If the fix is genuinely single-site, 1-2 angles is fine (different inputs).
- Each repro must be SELF-CONTAINED from the bug report; never reference a \
hidden grading test or any file under tests/.
- No code fences inside the JSON, no diffs.
- If no clean substring check is feasible at all, return {{"verifications": []}}."""

_JSON_RE = re.compile(r"```json\s*\n(.*?)```", re.DOTALL)


def _env() -> dict[str, str]:
    env = dict(os.environ)
    for key in _PROVIDER_ENV:
        env.pop(key, None)
    return env


def _extract_json(text: str) -> dict:
    m = _JSON_RE.search(text or "")
    blob = m.group(1) if m else None
    if blob is None:
        start, end = text.find("{"), text.rfind("}")
        blob = text[start : end + 1] if start != -1 and end != -1 else ""
    return json.loads(blob)


def _clean(text: str | None, gold: set[str]) -> tuple[str | None, int]:
    if not text:
        return None, 0
    c, r = scrub_leak(text, gold)
    return (c.strip() or None), r


def _clean_expected(value, gold: set[str]) -> tuple[object, int]:
    """`expected` may be a string OR a list of alternative substrings (any-of)."""
    if isinstance(value, list):
        cleaned: list[str] = []
        removed = 0
        for v in value:
            c, r = _clean(str(v) if v is not None else None, gold)
            removed += r
            if c:
                cleaned.append(c)
        if not cleaned:
            return None, removed
        return (cleaned[0] if len(cleaned) == 1 else cleaned), removed
    return _clean(value, gold)


def extract_one(iid: str, entry: dict, *, model: str, timeout: int) -> dict:
    cues = "\n".join(f"- {c}" for c in entry.get("localization_cues") or [])
    prompt = EXTRACT_PROMPT.format(
        verification_method=entry.get("verification_method", ""),
        root_cause_pattern=entry.get("root_cause_pattern", ""),
        cues=cues or "(none)",
    )
    cmd = [
        str(CLAUDE_BIN),
        "-p",
        prompt,
        "--output-format",
        "json",
        "--no-session-persistence",
        "--model",
        model,
        "--disallowedTools",
        "WebSearch",
        "WebFetch",
        "Bash",
        "Read",
        "Edit",
        "Write",
    ]
    with tempfile.TemporaryDirectory(prefix="agentbook-verify-") as cwd:
        r = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=_env()
        )
    payload = json.loads(r.stdout)
    raw = _extract_json(payload.get("result") or "")

    gold = gold_added_lines(iid)
    raw_list = (
        raw.get("verifications") if isinstance(raw.get("verifications"), list) else []
    )
    verifications: list[dict] = []
    leak_removed = 0
    for v in raw_list:
        if not isinstance(v, dict):
            continue
        cmd_clean, r1 = _clean(v.get("command"), gold)
        exp_clean, r2 = _clean_expected(v.get("expected"), gold)
        # Opus occasionally returns `buggy` as a list of alt markers too; reuse
        # the any-of cleaner and collapse a one-element list back to a string.
        bug_clean, r3 = _clean_expected(v.get("buggy"), gold)
        leak_removed += r1 + r2 + r3
        if not cmd_clean or not exp_clean:
            continue
        verifications.append(
            {
                "label": _clean(v.get("label"), gold)[0] or "",
                "command": cmd_clean,
                "expected": exp_clean,
                "buggy": bug_clean,
            }
        )

    out = dict(entry)
    out["verifications"] = verifications
    # Backwards-compat single fields: populate from the first repro so any
    # caller that reads the flat keys still works during the transition.
    first = verifications[0] if verifications else {}
    fexp = first.get("expected")
    out["verification_command"] = first.get("command")
    out["verification_expected"] = fexp[0] if isinstance(fexp, list) and fexp else fexp
    out["verification_buggy"] = first.get("buggy")
    out["verification_feasible"] = bool(verifications)
    out["verification_leak_removed"] = leak_removed
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract runnable verification checks")
    ap.add_argument("--model", default="opus")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    if not CLAUDE_BIN.exists():
        sys.exit(f"claude binary not found at {CLAUDE_BIN}")
    cache: dict[str, dict] = json.loads(SYNTH_CACHE.read_text())

    ids = list(cache)
    if args.only:
        ids = [i for i in ids if i in set(args.only)]
    todo = [i for i in ids if args.redo or "verification_feasible" not in cache[i]]
    print(f"extracting verification for {len(todo)}/{len(ids)} entries")

    lock = threading.Lock()

    def work(iid: str) -> tuple[str, str]:
        try:
            entry = extract_one(iid, cache[iid], model=args.model, timeout=args.timeout)
        except Exception as exc:  # noqa: BLE001
            return iid, f"ERROR {type(exc).__name__}: {exc}"
        with lock:
            cache[iid] = entry
            SYNTH_CACHE.write_text(
                json.dumps(cache, indent=2, ensure_ascii=False) + "\n"
            )
        ok = entry["verification_feasible"]
        return iid, f"feasible={ok} cmd={(entry['verification_command'] or '')[:50]!r}"

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(work, iid): iid for iid in todo}
        for fut in as_completed(futs):
            iid, msg = fut.result()
            done += 1
            print(f"[{done}/{len(todo)}] {iid}: {msg}", flush=True)

    feasible = sum(1 for e in cache.values() if e.get("verification_feasible"))
    print(
        f"\n{feasible}/{len(cache)} entries have a runnable verification -> {SYNTH_CACHE}"
    )


if __name__ == "__main__":
    main()
