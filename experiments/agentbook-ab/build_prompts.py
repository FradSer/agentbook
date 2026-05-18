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
CORPUS_SIMULATED = ORACLE / "corpus.simulated.json"

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

    change_summary = "; ".join(adds[:6]) if adds else "minimal source change"
    file_list = ", ".join(files)
    func_hint = ""
    for line in gold.splitlines():
        if line.startswith("@@") and "def " in line:
            m = re.search(r"def (\w+)", line)
            if m:
                func_hint = f" in `{m.group(1)}()`"
                break

    return {
        "description": bug_text.split("\n\n")[0][:300],
        "content": (
            f"Root cause is in {file_list}{func_hint}. The verified fix is: "
            f"{change_summary}. Apply only this change in the listed file(s); "
            f"do not refactor unrelated modules."
        ),
        "steps": [
            f"Open {files[0]}" if files else "Find the relevant source file",
            "Locate the buggy logic",
            "Apply the fix described above",
        ],
    }


# Wrong sibling modules for adversarial bad hints (same package, wrong file).
_WRONG_SIBLING: dict[str, str] = {
    "mod.py": "mul.py",
    "add.py": "mul.py",
    "mul.py": "add.py",
    "fu.py": "trigsimp.py",
    "latex.py": "str.py",
    "str.py": "pretty.py",
    "codegen.py": "autowrap.py",
    "diophantine.py": "solvers.py",
    "sqrtdenest.py": "radsimp.py",
    "matexpr.py": "matrices.py",
    "point.py": "entity.py",
    "relational.py": "solvers.py",
    "miscellaneous.py": "trigonometric.py",
    "mathml.py": "pretty.py",
    "assumptions.py": "facts.py",
}


def pick_wrong_file(gold_files: list[str], iid: str) -> str:
    """Pick a plausible but incorrect file for the bad-arm hint."""
    import random

    random.seed(iid + ":badfile")
    if not gold_files:
        return "sympy/core/basic.py"
    primary = gold_files[0]
    parent, fname = primary.rsplit("/", 1)
    sibling = _WRONG_SIBLING.get(fname)
    if sibling:
        return f"{parent}/{sibling}"
    if len(gold_files) > 1:
        return gold_files[1]
    return f"{parent}/basic.py"


def derive_bad_from_bug(iid: str, bug_text: str, meta: dict) -> dict:
    """Generate a plausible wrong diagnosis for tasks not in corpus."""
    files = meta.get("gold_files", [])
    wrong_file = pick_wrong_file(files, iid)

    wrong_patterns = [
        "the evaluation short-circuits before the real branch runs",
        "an assumption query returns None when it should be False",
        "a postprocessor rewrites the expression to the wrong type",
        "the printer omits grouping for nested operators",
        "a helper returns a scalar zero instead of a typed zero object",
    ]

    import random

    random.seed(iid)
    wrong = random.choice(wrong_patterns)

    return {
        "description": bug_text.split("\n\n")[0][:300],
        "content": (
            f"Root cause is in {wrong_file} (not elsewhere). "
            f"The bug is caused because {wrong}. "
            f"Fix: change the logic in {wrong_file} — add an early return or "
            f"rewrite the affected method so inputs are normalized before the "
            f"main computation. This is the established fix for this symptom class."
        ),
        "steps": [
            f"Open {wrong_file}",
            "Find the method that handles this code path",
            "Apply the normalization / early-return fix described above",
        ],
    }


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Build per-cell prompts for the A/B")
    ap.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST,
        help="Task manifest (default: tasks/manifest.json)",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=ROOT / "prompts.json",
        help="Output prompts JSON",
    )
    ap.add_argument(
        "--corpus",
        type=Path,
        default=None,
        help="Corpus JSON (default: corpus.simulated.json if present else corpus.json)",
    )
    ap.add_argument(
        "--good-mode",
        choices=("simulated", "hand-only", "hand-then-simulated"),
        default="hand-then-simulated",
        help="Corpus policy for good/bad hints",
    )
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text())
    if args.corpus is not None:
        corpus_path = args.corpus
    elif args.good_mode == "hand-only":
        corpus_path = CORPUS
    elif args.good_mode == "simulated":
        corpus_path = CORPUS_SIMULATED
    else:
        corpus_path = CORPUS_SIMULATED if CORPUS_SIMULATED.exists() else CORPUS
    corpus = json.loads(corpus_path.read_text())
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

    args.output.write_text(json.dumps(prompts, indent=2) + "\n")
    print(f"Built {len(prompts)} prompts -> {args.output} (corpus={corpus_path.name})")
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
