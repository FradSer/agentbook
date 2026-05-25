#!/usr/bin/env python
"""Synthesize leak-free prose memories into structured, weak-model-executable
knowledge -- the autoresearcher's job, isolated as the `good_synth` arm's corpus.

Input  : `_oracle/memories.json` (already leak-free; gold code stripped/scrubbed).
Output : `_oracle/synth_cache.json`, keyed by instance_id, each entry carrying

    root_cause_pattern   -- the transferable failure mode + fix DIRECTION
                            (a pattern a weak model can instantiate, NOT a patch).
    localization_cues    -- where to look (module / class / function / construct).
    verification_method  -- a runnable repro check (buggy vs expected behaviour)
                            the engineer can run themselves. Never the held-out
                            grading test.

Anti-leakage contract (same spine as memory/to_memory_entry.py):
  - Opus sees ONLY the leak-free memory, never gold.patch.
  - Every synthesized field is scrubbed against gold added lines anyway
    (defense in depth); `leak_lines_removed` records any hit.
  - We forbid fenced code / unified diffs in the output so it cannot smuggle a
    verbatim patch -- the whole point of good_synth is that the model derives the
    edit, not relays it.

Usage:
  uv run python -m memory.synthesize                 # all 17, skip cached
  uv run python -m memory.synthesize --only sympy__sympy-15017 --redo
  uv run python -m memory.synthesize --model opus --workers 4
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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from benchmark.paths import ORACLE  # noqa: E402

from memory.to_memory_entry import gold_added_lines, scrub_leak  # noqa: E402

CLAUDE_BIN = Path(os.path.expanduser("~/.local/bin/claude"))
MEMORIES_FILE = ORACLE / "memories.json"
SYNTH_CACHE = ORACLE / "synth_cache.json"

# Mirror the strong_solver: unset provider overrides so the real binary uses the
# default subscription credentials.
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

SYNTH_PROMPT = """You are a knowledge-synthesis agent for a shared memory layer \
used by AI coding agents. A peer agent fixed a Python bug and left the leak-free \
note below. Distill it into TRANSFERABLE, weak-model-actionable knowledge that \
lets a *much weaker* model re-derive and land the fix ITSELF -- not copy a patch.

Peer agent's note (already stripped of gold code):
---
PROBLEM: {description}

ROOT CAUSE + FIX (prose): {content}

REPRODUCTION / STEPS (prose): {steps}
---

Produce a JSON object with EXACTLY these three string-or-list-of-string fields:

- "root_cause_pattern": the failure MODE stated as a reusable pattern, plus the \
fix DIRECTION at a conceptual level (e.g. "an empty-product fallback returns the \
additive identity 0 instead of the multiplicative identity 1; the fix makes the \
empty case return the identity for the operation"). Name the class of mistake so \
a sibling bug would match it. Do NOT give a line-by-line patch.
- "localization_cues": a list of 2-5 short strings telling where to look -- \
module/file, class, function, and the code construct (e.g. "the `reduce(...)` over \
`shape` in the array constructors"). Symbols are fine; verbatim new source lines \
are not.
- "verification_method": ONE runnable check the engineer can paste into a shell \
or `python -c` to see the bug, plus the expected-vs-buggy outcome (e.g. \
"`python -c 'import sympy; print(len(sympy.Array(3)))'` prints 0 but should print \
1"). It MUST be self-contained from the bug report -- never reference a hidden \
grading test.

Hard rules:
- Output ONLY the JSON object inside a single ```json fenced block.
- NO unified diffs, NO ```diff blocks, NO multi-line code-to-paste-in. The weak \
model must synthesize the edit from your pattern, so do not hand it the edit.
- Keep each field tight; this is a memory entry, not an essay."""

_JSON_RE = re.compile(r"```json\s*\n(.*?)```", re.DOTALL)
_FENCE_ANY_RE = re.compile(r"```.*?```", re.DOTALL)


def _synth_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in _PROVIDER_ENV:
        env.pop(key, None)
    return env


def _extract_json(text: str) -> dict:
    """Pull the JSON object out of Opus's reply (fenced first, then first {...})."""
    m = _JSON_RE.search(text or "")
    blob = m.group(1) if m else None
    if blob is None:
        start = text.find("{")
        end = text.rfind("}")
        blob = text[start : end + 1] if start != -1 and end != -1 else ""
    return json.loads(blob)


def _normalize(raw: dict) -> dict:
    cues = raw.get("localization_cues")
    if isinstance(cues, str):
        cues = [cues]
    cues = [str(c).strip() for c in (cues or []) if str(c).strip()]
    return {
        "root_cause_pattern": str(raw.get("root_cause_pattern", "")).strip(),
        "localization_cues": cues[:5],
        "verification_method": str(raw.get("verification_method", "")).strip(),
    }


def _scrub_entry(entry: dict, gold: set[str]) -> tuple[dict, int]:
    """Defense-in-depth: drop fenced code and scrub gold lines from every field."""
    removed = 0

    def clean(text: str) -> str:
        nonlocal removed
        no_fence = _FENCE_ANY_RE.sub(" ", text)
        c, r = scrub_leak(no_fence, gold)
        removed += r
        return c

    out = {
        "root_cause_pattern": clean(entry["root_cause_pattern"]),
        "localization_cues": [clean(c) for c in entry["localization_cues"]],
        "verification_method": clean(entry["verification_method"]),
    }
    out["localization_cues"] = [c for c in out["localization_cues"] if c.strip()]
    return out, removed


def synthesize_one(mem: dict, *, model: str, timeout: int) -> dict:
    iid = mem["instance_id"]
    steps = "\n".join(mem.get("steps") or []) or "(none)"
    prompt = SYNTH_PROMPT.format(
        description=mem.get("description", ""),
        content=mem.get("content", ""),
        steps=steps,
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
    # Run in an empty temp dir so Claude Code does not auto-discover this repo's
    # CLAUDE.md (which would bias the synthesis with project instructions).
    with tempfile.TemporaryDirectory(prefix="agentbook-synth-") as cwd:
        t0 = time.time()
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_synth_env(),
        )
    payload = json.loads(r.stdout)
    result_text = payload.get("result") or ""
    entry = _normalize(_extract_json(result_text))

    gold = gold_added_lines(iid)
    entry, removed = _scrub_entry(entry, gold)
    entry.update(
        instance_id=iid,
        leak_lines_removed=removed,
        model=model,
        source="claude -p synthesis of leak-free memory",
        elapsed_s=round(time.time() - t0, 1),
    )
    return entry


def main() -> None:
    ap = argparse.ArgumentParser(description="Synthesize good_synth knowledge cache")
    ap.add_argument("--model", default="opus", help="claude model alias or id")
    ap.add_argument("--only", nargs="*", default=None, help="specific instance ids")
    ap.add_argument("--redo", action="store_true", help="re-synthesize cached entries")
    ap.add_argument("--timeout", type=int, default=300, help="per-task seconds")
    ap.add_argument("--workers", type=int, default=4, help="concurrent claude -p")
    args = ap.parse_args()

    if not CLAUDE_BIN.exists():
        sys.exit(f"claude binary not found at {CLAUDE_BIN}")

    memories = {m["instance_id"]: m for m in json.loads(MEMORIES_FILE.read_text())}
    cache: dict[str, dict] = (
        json.loads(SYNTH_CACHE.read_text()) if SYNTH_CACHE.exists() else {}
    )

    ids = list(memories)
    if args.only:
        ids = [i for i in ids if i in set(args.only)]
    todo = [i for i in ids if args.redo or i not in cache]
    print(f"synthesizing {len(todo)}/{len(ids)} memories with {args.workers} workers")

    lock = threading.Lock()

    def work(iid: str) -> tuple[str, dict | None, str]:
        try:
            entry = synthesize_one(
                memories[iid], model=args.model, timeout=args.timeout
            )
        except Exception as exc:  # noqa: BLE001 -- isolate one task's failure
            return iid, None, f"ERROR {type(exc).__name__}: {exc}"
        with lock:
            cache[iid] = entry
            SYNTH_CACHE.write_text(
                json.dumps(cache, indent=2, ensure_ascii=False) + "\n"
            )
        leak = entry["leak_lines_removed"]
        cues = len(entry["localization_cues"])
        return iid, entry, f"cues={cues} leak_removed={leak} ({entry['elapsed_s']}s)"

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(work, iid): iid for iid in todo}
        for fut in as_completed(futs):
            iid, entry, msg = fut.result()
            done += 1
            print(f"[{done}/{len(todo)}] {iid}: {msg}", flush=True)

    print(f"\nsynth cache -> {SYNTH_CACHE} ({len(cache)} entries)")


if __name__ == "__main__":
    main()
