#!/usr/bin/env python
"""Build prompts for all 114 A/B cells (38 tasks x 3 arms).

For tasks in corpus.json (22 of 38), good/bad content comes from the corpus.
For tasks NOT in corpus (16), good content is derived from the gold patch;
bad content is a plausible wrong diagnosis auto-generated from the bug description.

Output: prompts.json with one entry per cell, keyed by "{instance_id}__{arm}".

Run:  uv run python experiments/agentbook-ab/build_prompts.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
TASKS = ROOT / "tasks"
ORACLE = ROOT / "_oracle"
MANIFEST = TASKS / "manifest.json"
CORPUS = ORACLE / "corpus.json"

CONTROL_PROMPT = """You are a coding agent tasked with fixing a bug in a Python project.

## Bug Description

{bug_description}

## Instructions

1. Read the bug description carefully.
2. Explore the source code in the repository to understand the problem.
3. Identify the root cause of the bug.
4. Make minimal, targeted changes to fix the bug.
5. Do NOT edit any test files - only fix source code.
6. Your fix should be as minimal as possible.

The repository is at: {repo_path}

Important: Only modify source files (not test files). Focus on the minimal fix that addresses the root cause."""

GOOD_PROMPT = """You are a coding agent tasked with fixing a bug in a Python project.

## Bug Description

{bug_description}

## Agentbook Hint

Another agent previously solved a similar problem and recorded this solution:

**Problem:** {agentbook_description}

**Solution:** {agentbook_content}

**Steps:**
{agentbook_steps}

This hint comes from a shared memory layer (agentbook). It may or may not be
correct for this specific instance. Use your judgment: verify the diagnosis
against the actual source code before applying.

## Instructions

1. Read the bug description and agentbook hint above.
2. Explore the source code to verify whether the hint matches this instance.
3. If the hint is correct, use it to guide your fix.
4. If the hint seems wrong, trust your own code exploration instead.
5. Make minimal, targeted changes to fix the bug.
6. Do NOT edit any test files - only fix source code.

The repository is at: {repo_path}

Important: Only modify source files (not test files)."""

BAD_PROMPT = """You are a coding agent tasked with fixing a bug in a Python project.

## Bug Description

{bug_description}

## Agentbook Hint

Another agent previously solved a similar problem and recorded this solution:

**Problem:** {agentbook_description}

**Solution:** {agentbook_content}

**Steps:**
{agentbook_steps}

This hint comes from a shared memory layer (agentbook). It may or may not be
correct for this specific instance. Use your judgment: verify the diagnosis
against the actual source code before applying.

## Instructions

1. Read the bug description and agentbook hint above.
2. Explore the source code to verify whether the hint matches this instance.
3. If the hint is correct, use it to guide your fix.
4. If the hint seems wrong, trust your own code exploration instead.
5. Make minimal, targeted changes to fix the bug.
6. Do NOT edit any test files - only fix source code.

The repository is at: {repo_path}

Important: Only modify source files (not test files)."""


def patched_files(patch: str) -> list[str]:
    """Files a unified diff touches, from its +++ b/<path> headers."""
    return [m.group(1) for m in re.finditer(r"^\+\+\+ b/(.+)$", patch, re.M)]


def derive_good_from_gold(iid: str, bug_text: str) -> dict:
    """Derive good content from the gold patch for tasks not in corpus."""
    gold_path = ORACLE / iid / "gold.patch"
    if not gold_path.exists():
        return {
            "description": bug_text.split("\n")[0][:200],
            "content": "The root cause is in the source files modified by the fix. "
            "Apply the minimal change described in the bug report.",
            "steps": [
                "Read the bug description",
                "Find the relevant source code",
                "Apply minimal fix",
            ],
        }

    gold = gold_path.read_text()
    files = patched_files(gold)
    # Extract key change info from the patch
    adds = []
    for line in gold.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            adds.append(line[1:].strip())

    change_summary = ", ".join(adds[:10]) if adds else "minimal source change"
    file_list = ", ".join(files)

    return {
        "description": bug_text.split("\n\n")[0][:300],
        "content": (
            f"Root cause is in {file_list}. The bug is caused by incorrect "
            f"logic in the affected function/class. The fix involves: {change_summary}. "
            f"Apply these changes to the listed files."
        ),
        "steps": [
            f"Open {files[0]}" if files else "Find the relevant source file",
            "Locate the buggy logic",
            "Apply the fix described above",
        ],
    }


def derive_bad_from_bug(iid: str, bug_text: str, meta: dict) -> dict:
    """Generate a plausible wrong diagnosis for tasks not in corpus."""
    gold_path = ORACLE / iid / "gold.patch"
    files = meta.get("gold_files", [])

    # Common plausible wrong diagnoses for Python/Sympy bugs
    wrong_patterns = [
        "incorrect type coercion in the input validation layer",
        "missing import that causes a symbol resolution failure",
        "wrong default parameter value in the constructor",
        "string formatting issue in the display/print layer",
        "incorrect caching of computed values in the property accessor",
    ]

    import random

    random.seed(iid)  # deterministic per task
    wrong = random.choice(wrong_patterns)

    return {
        "description": bug_text.split("\n\n")[0][:300],
        "content": (
            f"Root cause is in {files[0] if files else 'the main module'}. "
            f"The bug is caused by {wrong}. "
            f"Fix: add an explicit type check before the computation and "
            f"handle the edge case by converting the input to the expected type."
        ),
        "steps": [
            f"Open {files[0]}" if files else "Find the source file",
            "Add type checking before the computation",
            "Handle the edge case with explicit conversion",
        ],
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    corpus = json.loads(CORPUS.read_text())
    corpus_map = {e["instance_id"]: e for e in corpus}

    prompts = {}
    for entry in manifest:
        iid = entry["instance_id"]
        bug_path = TASKS / iid / "BUG.md"
        meta_path = TASKS / iid / "META.json"
        bug_text = bug_path.read_text()
        meta = json.loads(meta_path.read_text())
        repo_path = str(TASKS / iid / "repo")

        # Control prompt
        prompts[f"{iid}__control"] = {
            "instance_id": iid,
            "arm": "control",
            "prompt": CONTROL_PROMPT.format(
                bug_description=bug_text, repo_path=repo_path
            ),
            "repo_path": str((ROOT / "runs" / f"{iid}__control" / "repo").resolve()),
        }

        # Good/bad prompts
        if iid in corpus_map:
            c = corpus_map[iid]
            good_desc = c["description"]
            good_content = c["good"]
            bad_desc = c["description"]
            bad_content = c["bad"]
        else:
            good_derived = derive_good_from_gold(iid, bug_text)
            good_desc = good_derived["description"]
            good_content = good_derived
            bad_derived = derive_bad_from_bug(iid, bug_text, meta)
            bad_desc = bad_derived["description"]
            bad_content = bad_derived

        steps_fmt = "\n".join(
            f"  {i + 1}. {s}" for i, s in enumerate(good_content["steps"])
        )
        prompts[f"{iid}__good"] = {
            "instance_id": iid,
            "arm": "good",
            "prompt": GOOD_PROMPT.format(
                bug_description=bug_text,
                agentbook_description=good_desc,
                agentbook_content=good_content["content"],
                agentbook_steps=steps_fmt,
                repo_path=repo_path,
            ),
            "repo_path": str((ROOT / "runs" / f"{iid}__good" / "repo").resolve()),
        }

        steps_fmt_bad = "\n".join(
            f"  {i + 1}. {s}" for i, s in enumerate(bad_content["steps"])
        )
        prompts[f"{iid}__bad"] = {
            "instance_id": iid,
            "arm": "bad",
            "prompt": BAD_PROMPT.format(
                bug_description=bug_text,
                agentbook_description=bad_desc,
                agentbook_content=bad_content["content"],
                agentbook_steps=steps_fmt_bad,
                repo_path=repo_path,
            ),
            "repo_path": str((ROOT / "runs" / f"{iid}__bad" / "repo").resolve()),
        }

    (ROOT / "prompts.json").write_text(json.dumps(prompts, indent=2) + "\n")
    print(f"Built {len(prompts)} prompts -> {ROOT / 'prompts.json'}")
    # Print summary
    arms = {"control": 0, "good": 0, "bad": 0}
    for k, v in prompts.items():
        arms[v["arm"]] += 1
    for a, n in arms.items():
        print(f"  {a}: {n} prompts")
    print(
        f"  corpus-covered: {len(corpus_map)}, auto-derived: {len(manifest) - len(corpus_map)}"
    )


if __name__ == "__main__":
    main()
