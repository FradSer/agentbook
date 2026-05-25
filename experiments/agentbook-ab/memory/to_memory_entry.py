#!/usr/bin/env python
"""Convert a VERIFIED strong-solver solution into a leakage-free memory entry.

Anti-leakage contract (this is what the OLD eval violated):
  - description / error_signature come from the agent-visible BUG.md only.
  - content is the solver's PROSE narrative (root cause + conceptual fix).
  - all fenced code blocks are stripped, and any line copied verbatim from the
    held-out gold.patch added lines is scrubbed (with a count recorded), so no
    gold code can leak into the `good` arm.
  - tags are semantic/domain only (from BUG.md keywords) -- no per-task tag.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from benchmark.bugfields import extract_bug_fields  # noqa: E402
from benchmark.paths import ORACLE, TASKS  # noqa: E402

_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_SECTION_RE = re.compile(
    r"ROOT CAUSE:\s*(?P<root>.*?)\s*FIX:\s*(?P<fix>.*?)\s*STEPS:\s*(?P<steps>.*)",
    re.DOTALL | re.IGNORECASE,
)


def gold_added_lines(iid: str) -> set[str]:
    """Non-trivial added (`+`) source lines from the held-out gold.patch."""
    patch = (ORACLE / iid / "gold.patch").read_text(errors="replace")
    out: set[str] = set()
    for line in patch.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            stripped = line[1:].strip()
            if len(stripped) >= 8 and not stripped.startswith(("#", '"""', "'''")):
                out.add(stripped)
    return out


def scrub_leak(text: str, gold_lines: set[str]) -> tuple[str, int]:
    """Remove gold code from the narrative: drop fenced code blocks, lines
    verbatim-equal to a gold added line, AND gold fragments that appear as
    substrings inside prose (replaced with an ellipsis). Returns (clean, count).
    """
    no_fences = _FENCE_RE.sub(" ", text)
    kept: list[str] = []
    removed = 0
    for line in no_fences.splitlines():
        if line.strip() in gold_lines:
            removed += 1
            continue
        kept.append(line)
    out = "\n".join(kept)
    # neutralize any remaining verbatim gold fragments embedded in prose
    for g in sorted((g for g in gold_lines if len(g) >= 8), key=len, reverse=True):
        if g in out:
            out = out.replace(g, "…")
            removed += 1
    clean = re.sub(r"\n{3,}", "\n\n", out).strip()
    return clean, removed


def _parse_sections(text: str) -> tuple[str, str, list[str]]:
    m = _SECTION_RE.search(text)
    if not m:
        return "", "", []
    root = re.sub(r"\s+", " ", m.group("root")).strip()
    fix = re.sub(r"\s+", " ", m.group("fix")).strip()
    steps_raw = m.group("steps").strip()
    steps: list[str] = []
    for line in steps_raw.splitlines():
        s = re.sub(r"^\s*(\d+[.)]|[-*])\s*", "", line).strip()
        if s:
            steps.append(s)
    return root, fix, steps


def build_entry(iid: str) -> dict:
    bug = (TASKS / iid / "BUG.md").read_text()
    description, error_signature, tags = extract_bug_fields(bug)
    sol_text = (
        Path(__import__("tempfile").gettempdir())
        / "agentbook-ab-solver"
        / f"{iid}__solver"
        / "solution.md"
    ).read_text(errors="replace")

    gold = gold_added_lines(iid)
    root, fix, steps = _parse_sections(sol_text)
    if root or fix:
        content = f"Root cause: {root}\n\nFix: {fix}".strip()
    else:
        # Solver did not follow the format; fall back to its scrubbed narrative.
        content, _ = scrub_leak(sol_text, gold)
        content = content[:1200]

    content, removed_c = scrub_leak(content, gold)
    clean_steps: list[str] = []
    removed_s = 0
    for st in steps:
        cs, r = scrub_leak(st, gold)
        removed_s += r
        if cs.strip():
            clean_steps.append(cs.strip()[:300])

    return {
        "instance_id": iid,
        "description": description,
        "error_signature": error_signature,
        "tags": tags,
        "content": content,
        "steps": clean_steps[:8],
        "leak_lines_removed": removed_c + removed_s,
    }
