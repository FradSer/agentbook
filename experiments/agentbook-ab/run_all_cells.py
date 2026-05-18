#!/usr/bin/env python
"""Run all 114 A/B cells (38 tasks x 3 arms) via OpenRouter Claude Haiku 4.5.

Each cell gets a rich prompt that includes:
  - The bug description (BUG.md)
  - For good/bad arms: the agentbook hint from the corpus or auto-derived
  - Pre-loaded source files from gold_files (so Haiku has context without
    needing to explore)
  - A request for a unified diff output format

The script parses Haiku's response, extracts code changes, applies them
to the run repo, and commits.

This runs outside the Claude Code agent framework, directly via the
OpenRouter API, avoiding the glm-5.1 rate limit that blocks sub-agents.

Run:  cd /Users/FradSer/Developer/FradSer/agentbook && \
      uv run --with openai python experiments/agentbook-ab/run_all_cells.py [--arm ARM] [--task TASK_ID]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent / "experiments" / "agentbook-ab"
TASKS = ROOT / "tasks"
ORACLE = ROOT / "_oracle"
RUNS = ROOT / "runs"
MANIFEST = TASKS / "manifest.json"
_CORPUS_SIM = ORACLE / "corpus.simulated.json"
CORPUS = _CORPUS_SIM if _CORPUS_SIM.exists() else ORACLE / "corpus.json"
PROMPTS_FILE = ROOT / "prompts.json"

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
MODEL = "anthropic/claude-3.5-haiku-20241022"  # Claude Haiku 4.5
MAX_TOKENS = 16384
TIMEOUT_SECONDS = 300  # 5 minutes per task
DELAY_BETWEEN_TASKS = 5  # seconds between API calls


def load_env() -> str:
    """Load OPENROUTER_API_KEY from .env file or env vars."""
    env_file = Path(__file__).parent.parent.parent / ".env"
    key = ""
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not key:
        key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not found")
    return key


def call_haiku(api_key: str, prompt: str) -> str:
    """Call Claude Haiku via OpenRouter with the openai SDK."""
    from openai import OpenAI

    client = OpenAI(base_url=OPENROUTER_BASE, api_key=api_key)
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
                timeout=TIMEOUT_SECONDS,
            )
            return response.choices[0].message.content
        except Exception as exc:
            if attempt < 2:
                print(f"  API error (attempt {attempt + 1}): {exc}; retrying in 30s...")
                time.sleep(30)
            else:
                raise


def prepare_run_dir(iid: str, arm: str) -> Path:
    """Prepare the run directory from pristine task repo."""
    run_dir = RUNS / f"{iid}__{arm}"
    run_repo = run_dir / "repo"
    if run_repo.exists():
        shutil.rmtree(run_repo)
    run_repo.mkdir(parents=True)
    src_repo = TASKS / iid / "repo"
    shutil.copytree(src_repo, run_repo, dirs_exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=run_repo, capture_output=True, timeout=30)
    subprocess.run(
        ["git", "config", "user.email", "bench@local"],
        cwd=run_repo,
        capture_output=True,
        timeout=30,
    )
    subprocess.run(
        ["git", "config", "user.name", "bench"],
        cwd=run_repo,
        capture_output=True,
        timeout=30,
    )
    subprocess.run(["git", "add", "-A"], cwd=run_repo, capture_output=True, timeout=60)
    subprocess.run(
        ["git", "commit", "-q", "-m", "base"],
        cwd=run_repo,
        capture_output=True,
        timeout=60,
    )
    return run_repo


def load_source_files(repo_path: Path, meta: dict, max_chars: int = 15000) -> str:
    """Load key source files from the repo into the prompt."""
    gold_files = meta.get("gold_files", [])
    test_files = meta.get("test_files", [])
    # Load gold_files first, then a few other relevant files
    loaded = []
    total = 0
    for gf in gold_files:
        fpath = repo_path / gf
        if fpath.exists() and total < max_chars:
            content = fpath.read_text(errors="replace")
            loaded.append(f"### File: {gf}\n```python\n{content}\n```")
            total += len(content)
    # Also load any files mentioned in the bug description
    bug_text = (TASKS / meta["instance_id"] / "BUG.md").read_text()
    for match in re.finditer(r"([\w/.]+\.py)", bug_text):
        fname = match.group(1)
        fpath = repo_path / fname
        if fpath.exists() and fname not in gold_files and total < max_chars:
            content = fpath.read_text(errors="replace")
            loaded.append(f"### File: {fname}\n```python\n{content}\n```")
            total += len(content)
    return "\n\n".join(loaded) if loaded else ""


def build_prompt(iid: str, arm: str, meta: dict, bug_text: str) -> str:
    """Build the rich prompt for a cell."""
    repo_path = TASKS / iid / "repo"
    source_context = load_source_files(repo_path, meta)

    # Load corpus for good/bad arms
    corpus = json.loads(CORPUS.read_text())
    corpus_map = {e["instance_id"]: e for e in corpus}

    agentbook_section = ""
    if arm == "good" and iid in corpus_map:
        c = corpus_map[iid]
        steps = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(c["good"]["steps"]))
        agentbook_section = f"""
## Agentbook Hint (accurate solution from a prior agent)

**Problem description:** {c["description"]}

**Root cause and fix:** {c["good"]["content"]}

**Steps:**
{steps}

This hint comes from agentbook's shared memory. It may be correct for this
instance. Verify it against the source code, but if it matches, use it to guide your fix.
"""
    elif arm == "bad" and iid in corpus_map:
        c = corpus_map[iid]
        steps = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(c["bad"]["steps"]))
        agentbook_section = f"""
## Agentbook Hint (from a prior agent)

**Problem description:** {c["description"]}

**Root cause and fix:** {c["bad"]["content"]}

**Steps:**
{steps}

This hint comes from agentbook's shared memory. It may or may not be correct.
Verify it against the source code before applying.
"""
    elif arm == "good" and iid not in corpus_map:
        # Derive from gold patch
        gold_path = ORACLE / iid / "gold.patch"
        if gold_path.exists():
            gold = gold_path.read_text()
            files = [m.group(1) for m in re.finditer(r"^\+\+\+ b/(.+)$", gold, re.M)]
            adds = [
                l[1:].strip()
                for l in gold.splitlines()
                if l.startswith("+") and not l.startswith("+++")
            ]
            change_summary = ", ".join(adds[:5])
            agentbook_section = f"""
## Agentbook Hint

The root cause is in {", ".join(files)}. The fix involves: {change_summary}.
Apply these minimal changes to the listed files.
"""
    elif arm == "bad" and iid not in corpus_map:
        files = meta.get("gold_files", [])
        agentbook_section = f"""
## Agentbook Hint

The root cause appears to be an incorrect type coercion in the input validation.
Fix: add explicit type checking before the computation in {files[0] if files else "the main module"}.
"""

    project = meta.get("repo", "sympy/sympy").split("/")[-1]
    prompt = f"""You are a coding agent fixing a bug in a Python project ({project}).

## Bug Description

{bug_text}

{agentbook_section}

## Relevant Source Code

{source_context}

## Instructions

1. Analyze the bug description and the provided source code.
2. Identify the root cause of the bug.
3. Produce a minimal fix as a **unified diff** format.
4. Do NOT modify any test files.
5. The fix should be as minimal as possible.

## Output Format

Output ONLY the unified diff for each file you want to change.
Use the standard unified diff format:

```diff
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -line,count +line,count @@
 context line
-removed line
+added line
```

If you need to change multiple files, output multiple diff blocks.
After all diffs, write a brief explanation of the root cause and fix."""

    return prompt


def apply_diff(run_repo: Path, diff_text: str) -> bool:
    """Parse and apply unified diff from Haiku's response."""
    # Write diff to temp file and try git apply
    diff_file = run_repo / "_haiku_diff.patch"
    diff_file.write_text(diff_text)

    # Try git apply with various options
    for attempt_args in [
        ["git", "apply", "--allow-empty", "_haiku_diff.patch"],
        ["git", "apply", "-3", "_haiku_diff.patch"],  # 3-way merge
        ["git", "apply", "--reject", "_haiku_diff.patch"],  # Apply with rejects
    ]:
        r = subprocess.run(
            attempt_args, cwd=run_repo, capture_output=True, text=True, timeout=30
        )
        if r.returncode == 0:
            diff_file.unlink(missing_ok=True)
            return True

    # If git apply failed, try manual string replacement approach
    # Parse diff blocks and apply changes directly
    blocks = re.findall(
        r"---\s+a/(.*?)\n\+\+\+\s+b/(.*?)\n(?:@@.*?@@\n)((?:[ +\-].*?\n)+)",
        diff_text,
        re.MULTILINE,
    )
    applied_any = False
    for old_path, new_path, changes_text in blocks:
        target_path = new_path
        file_path = run_repo / target_path
        if not file_path.exists():
            continue
        original = file_path.read_text(errors="replace")
        # Extract removals and additions
        lines = changes_text.splitlines()
        new_lines = []
        for line in lines:
            if line.startswith(" ") or line.startswith("+"):
                new_lines.append(line[1:])
            # Skip lines starting with "-" (removals)

        # Try to find and replace the context block
        context_lines = [l[1:] for l in lines if l.startswith(" ")]
        removed_lines = [l[1:] for l in lines if l.startswith("-")]

        if context_lines and removed_lines:
            # Find the block in the original file and replace
            context_block = "\n".join(context_lines)
            replacement = "\n".join(new_lines)
            if context_block in original:
                original = original.replace(context_block, replacement, 1)
                file_path.write_text(original)
                applied_any = True

    diff_file.unlink(missing_ok=True)
    return applied_any


def apply_code_blocks(run_repo: Path, response: str) -> bool:
    """Fallback: parse code blocks with file path annotations and apply."""
    # Look for patterns like:
    # "In file sympy/core/numbers.py, change X to Y"
    # Or ```python blocks preceded by file path references
    applied = False

    # Find all code blocks
    code_blocks = re.findall(r"```(?:python)?\n(.*?)```", response, re.DOTALL)
    file_refs = re.findall(r"([\w/.]+\.py)", response)

    # This is a rough fallback - if we have exactly one code block and one
    # file reference, replace the entire file
    if len(code_blocks) == 1 and len(file_refs) >= 1:
        target = file_refs[0]
        file_path = run_repo / target
        if file_path.exists():
            new_content = code_blocks[0]
            file_path.write_text(new_content)
            applied = True

    return applied


def run_cell(iid: str, arm: str, api_key: str) -> dict:
    """Run a single cell via OpenRouter."""
    bug_text = (TASKS / iid / "BUG.md").read_text()
    meta = json.loads((TASKS / iid / "META.json").read_text())

    # Prepare run directory
    run_repo = prepare_run_dir(iid, arm)

    run_dir = RUNS / f"{iid}__{arm}"
    prepared = run_dir / "prompt.md"
    if prepared.exists():
        prompt = prepared.read_text()
    else:
        prompt = build_prompt(iid, arm, meta, bug_text)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt_used.md").write_text(prompt)

    # Call Haiku
    print(f"  Calling Haiku for {iid} [{arm}]...", flush=True)
    try:
        response = call_haiku(api_key, prompt)
    except Exception as exc:
        return {
            "instance_id": iid,
            "arm": arm,
            "status": "api_error",
            "error": str(exc),
        }

    # Save response
    (RUNS / f"{iid}__{arm}" / "haiku_response.md").write_text(response)

    # Try to extract and apply diff
    diff_match = re.search(r"```diff\n(.*?)```", response, re.DOTALL)
    if diff_match:
        diff_text = diff_match.group(1)
        # Add proper diff headers if missing
        if not diff_text.startswith("---"):
            diff_text = "--- a/\n+++ b/\n" + diff_text
        applied = apply_diff(run_repo, diff_text)
    else:
        # Try full response as diff
        applied = apply_diff(run_repo, response)
        if not applied:
            # Fallback to code block parsing
            applied = apply_code_blocks(run_repo, response)

    if applied:
        subprocess.run(
            ["git", "add", "-A"], cwd=run_repo, capture_output=True, timeout=60
        )
        subprocess.run(
            ["git", "commit", "-q", "-m", "haiku-fix"],
            cwd=run_repo,
            capture_output=True,
            timeout=60,
        )

    return {
        "instance_id": iid,
        "arm": arm,
        "status": "completed",
        "fix_applied": applied,
        "response_length": len(response),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all A/B cells via OpenRouter")
    parser.add_argument(
        "--arm", choices=["control", "good", "bad", "all"], default="all"
    )
    parser.add_argument("--task", help="Specific task ID")
    parser.add_argument(
        "--skip-done",
        action="store_true",
        help="Skip cells that already have fix commits",
    )
    args = parser.parse_args()

    api_key = load_env()
    manifest = json.loads(MANIFEST.read_text())

    arms = ["control", "good", "bad"] if args.arm == "all" else [args.arm]
    tasks = [args.task] if args.task else [e["instance_id"] for e in manifest]

    cells = []
    for iid in tasks:
        for arm in arms:
            # Check if already done
            if args.skip_done:
                run_repo = RUNS / f"{iid}__{arm}" / "repo"
                r = subprocess.run(
                    ["git", "log", "--oneline"],
                    cwd=run_repo,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                commits = r.stdout.strip().split("\n")
                if len(commits) > 1:
                    print(f"  SKIP {iid} [{arm}] (already done)")
                    continue
            cells.append((iid, arm))

    print(f"Running {len(cells)} cells via OpenRouter Claude Haiku 4.5")
    results = []
    for i, (iid, arm) in enumerate(cells):
        print(f"\n[{i + 1}/{len(cells)}] {iid} [{arm}]...", flush=True)
        result = run_cell(iid, arm, api_key)
        results.append(result)
        print(
            f"  -> {result['status']} (fix_applied={result.get('fix_applied')})",
            flush=True,
        )

        if i < len(cells) - 1:
            time.sleep(DELAY_BETWEEN_TASKS)

    # Save results
    results_file = ROOT / "cell_run_results.json"
    results_file.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nResults saved to {results_file}")

    # Summary
    applied_count = sum(1 for r in results if r.get("fix_applied"))
    print(f"Fixes applied: {applied_count}/{len(results)}")


if __name__ == "__main__":
    main()
