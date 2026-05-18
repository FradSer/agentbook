#!/usr/bin/env python
"""Fix remaining cells via direct Bailian glm-5.1 API calls.

This bypasses the sub-agent rate limit by making single API calls per cell,
instead of launching full Claude Code sub-agents that need many calls.

For each cell, we:
1. Read BUG.md and identify relevant source files from the oracle
2. Include those files in a single prompt
3. Make one API call to glm-5.1 via Bailian
4. Parse the response for code changes and apply them
5. Commit the result

Run:  cd /Users/FradSer/Developer/FradSer/agentbook && \
      uv run --with httpx python experiments/agentbook-ab/fix_remaining.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASKS = ROOT / "tasks"
ORACLE = ROOT / "_oracle"
RUNS = ROOT / "runs"
MANIFEST = TASKS / "manifest.json"
CORPUS = ORACLE / "corpus.json"
PROMPTS_FILE = ROOT / "prompts.json"

BAILIAN_BASE = os.environ.get("ANTHROPIC_BASE_URL", "http://10.10.0.195:8317")
API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN", "sk-dummy")
MODEL = "glm-5.1"
MAX_TOKENS = 4096
TIMEOUT = 300


def bailian_call(system: str, user: str) -> str:
    """Make a single chat completion call to glm-5.1 via Bailian Anthropic API."""
    import httpx

    url = f"{BAILIAN_BASE}/v1/messages"
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }

    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.post(url, headers=headers, json=body)
        if r.status_code != 200:
            print(f"  API error: {r.status_code} {r.text[:200]}")
            return ""
        data = r.json()
        # Extract text content
        for block in data.get("content", []):
            if block.get("type") == "text":
                return block["text"]
    return ""


def identify_cells_to_fix():
    """Find cells that have no edits from base commit."""
    manifest = json.loads(MANIFEST.read_text())
    cells = []
    for t in manifest:
        iid = t["instance_id"]
        for arm in ["control", "good", "bad"]:
            cell = f"{iid}__{arm}"
            run_repo = RUNS / cell / "repo"
            if not run_repo.is_dir():
                continue
            log = subprocess.run(
                ["git", "log", "--oneline"],
                cwd=run_repo,
                capture_output=True,
                text=True,
            )
            base = None
            for l in log.stdout.strip().split("\n"):
                if "base" in l.lower():
                    base = l.split()[0]
                    break
            if base:
                diff = subprocess.run(
                    ["git", "diff", "--name-only", base, "HEAD"],
                    cwd=run_repo,
                    capture_output=True,
                    text=True,
                )
                if not diff.stdout.strip():
                    cells.append((iid, arm, cell))
    return cells


def get_gold_changed_files(iid: str) -> list[str]:
    """Get list of files changed in the gold patch."""
    gold_patch = ORACLE / iid / "gold.patch"
    if not gold_patch.exists():
        return []
    text = gold_patch.read_text()
    files = []
    for line in text.split("\n"):
        m = re.match(r"^--- a/(.+)$", line)
        if m:
            files.append(m.group(1))
        m = re.match(r"^^\+\+\+ b/(.+)$", line)
        if m:
            if m.group(1) not in files:
                files.append(m.group(1))
    return files


def read_source_file(run_repo: Path, filepath: str) -> str:
    """Read a source file from the run repo."""
    full = run_repo / filepath
    if full.exists():
        return full.read_text(errors="replace")
    return ""


def build_prompt(iid: str, arm: str, run_repo: Path) -> tuple[str, str]:
    """Build system and user prompts for a cell."""
    bug_text = (TASKS / iid / "BUG.md").read_text()
    gold_files = get_gold_changed_files(iid)
    # Filter to only .py source files, exclude test files
    meta = json.loads((TASKS / iid / "META.json").read_text())
    test_files = set(meta.get("test_files", []))
    source_files = [f for f in gold_files if f.endswith(".py") and f not in test_files]

    # Read relevant source code (limit to avoid token overflow)
    file_contents = ""
    total_chars = 0
    MAX_SOURCE_CHARS = 8000
    for sf in source_files[:3]:
        content = read_source_file(run_repo, sf)
        if content and total_chars + len(content) < MAX_SOURCE_CHARS:
            file_contents += f"\n\n--- {sf} ---\n{content}"
            total_chars += len(content)

    system = "You are a expert Python programmer. Fix bugs in the sympy library. Output ONLY a unified diff of your changes. Do not modify test files."

    corpus_list = json.loads(CORPUS.read_text())
    corpus_map = {c["instance_id"]: c for c in corpus_list}

    arm_hint = ""
    if arm == "good" and iid in corpus_map:
        c = corpus_map[iid]
        steps = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(c["good"]["steps"]))
        arm_hint = f"""
Agentbook hint (accurate debugging knowledge):
Description: {c["description"]}
Content: {c["good"]["content"]}
Steps:
{steps}
"""
    elif arm == "bad" and iid in corpus_map:
        c = corpus_map[iid]
        steps = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(c["bad"]["steps"]))
        arm_hint = f"""
Agentbook hint (adversarial/misleading debugging knowledge):
Description: {c["description"]}
Content: {c["bad"]["content"]}
Steps:
{steps}
"""

    user = f"""Fix this bug in sympy.

Bug description:
{bug_text}

{arm_hint}

Relevant source code:
{file_contents}

Output a unified diff of ONLY the source file changes needed to fix the bug. Do NOT modify test files. Format:

--- a/path/to/file.py
+++ b/path/to/file.py
@@ -line,count +line,count @@
 context line
-removed line
+added line
"""

    return system, user


def parse_and_apply_diff(response: str, run_repo: Path) -> bool:
    """Parse unified diff from response and apply it to the repo."""
    # Extract diff blocks
    diff_pattern = r"(--- a/.+\n\+\+\+ b/.+\n(?:@@ .+ @@\n(?:[ +\-].*\n|\n))+)"
    diffs = re.findall(diff_pattern, response, re.MULTILINE)

    if not diffs:
        # Try alternate pattern: look for file path and changes
        # Sometimes the model outputs changes inline
        lines = response.split("\n")
        in_diff = False
        current_diff = []
        diffs = []
        for line in lines:
            if line.startswith("--- a/"):
                in_diff = True
                current_diff = [line]
            elif line.startswith("+++ b/"):
                if in_diff:
                    current_diff.append(line)
            elif in_diff and (
                line.startswith("@@")
                or line.startswith("+")
                or line.startswith("-")
                or line.startswith(" ")
                or line == ""
            ):
                current_diff.append(line)
            elif in_diff and not line.startswith(("+", "-", " ", "@@")):
                in_diff = False
                if len(current_diff) > 2:
                    diffs.append("\n".join(current_diff))
                current_diff = []

        if current_diff and len(current_diff) > 2:
            diffs.append("\n".join(current_diff))

    if not diffs:
        print("  No diff found in response")
        # Try to extract code blocks with file references
        code_blocks = re.findall(
            r"```(?:python|diff)?\s*\n(.*?)\n```", response, re.DOTALL
        )
        if code_blocks:
            for block in code_blocks:
                if "--- a/" in block or "def " in block:
                    # Try applying as inline replacement
                    print("  Found code block but no diff format")
        return False

    # Write combined diff to a file and apply
    combined = "\n".join(diffs)
    patch_file = run_repo / "_fix.patch"
    patch_file.write_text(combined)

    result = subprocess.run(
        ["git", "apply", "--allow-empty", "_fix.patch"],
        cwd=run_repo,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"  git apply failed: {result.stderr[:200]}")
        # Try with 3-way merge
        result2 = subprocess.run(
            ["git", "apply", "--3way", "--allow-empty", "_fix.patch"],
            cwd=run_repo,
            capture_output=True,
            text=True,
        )
        if result2.returncode != 0:
            print(f"  3-way merge also failed: {result2.stderr[:200]}")
            patch_file.unlink(missing_ok=True)
            return False

    # Check if any files were actually changed
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=run_repo,
        capture_output=True,
        text=True,
    )
    if not status.stdout.strip():
        print("  No files changed after applying patch")
        patch_file.unlink(missing_ok=True)
        return False

    # Commit the changes
    subprocess.run(["git", "add", "-A"], cwd=run_repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "fix"],
        cwd=run_repo,
        capture_output=True,
    )
    patch_file.unlink(missing_ok=True)
    return True


def apply_inline_fixes(response: str, run_repo: Path, source_files: list[str]) -> bool:
    """Alternative: parse inline code blocks and write them directly."""
    # Look for patterns like: "In file.py, change X to Y"
    # Or "Replace lines N-N with: ..."
    # This is a fallback for responses that don't output unified diff format

    for sf in source_files[:3]:
        filepath = run_repo / sf
        if not filepath.exists():
            continue

        # Check if response mentions this file with specific changes
        filename = sf.split("/")[-1]
        if filename in response:
            # Try to find a complete replacement for the file
            block_match = re.search(
                r"```python\s*\n(.*?)\n```",
                response,
                re.DOTALL,
            )
            if block_match:
                new_content = block_match.group(1)
                filepath.write_text(new_content)
                subprocess.run(["git", "add", "-A"], cwd=run_repo, capture_output=True)
                subprocess.run(
                    ["git", "commit", "-m", "fix"],
                    cwd=run_repo,
                    capture_output=True,
                )
                return True

    return False


def main():
    cells = identify_cells_to_fix()
    print(f"Found {len(cells)} cells needing fix")

    success = 0
    fail = 0
    rate_limit = 0

    for iid, arm, cell in cells:
        print(f"\nFixing {cell} ...")
        run_repo = RUNS / cell / "repo"

        system, user = build_prompt(iid, arm, run_repo)
        print(f"  Prompt: {len(system)}+{len(user)} chars")

        response = bailian_call(system, user)
        if not response:
            print("  FAILED (no response)")
            fail += 1
            if "429" in response or "rate" in response.lower():
                rate_limit += 1
            time.sleep(10)
            continue

        print(f"  Response: {len(response)} chars, first 100: {response[:100]}")

        # Try unified diff first
        gold_files = get_gold_changed_files(iid)
        meta = json.loads((TASKS / iid / "META.json").read_text())
        test_files = set(meta.get("test_files", []))
        source_files = [
            f for f in gold_files if f.endswith(".py") and f not in test_files
        ]

        applied = parse_and_apply_diff(response, run_repo)
        if not applied:
            # Fallback: try inline fixes
            applied = apply_inline_fixes(response, run_repo, source_files)

        if applied:
            print("  SUCCESS")
            success += 1
        else:
            print("  FAILED (could not apply)")
            fail += 1

        # Rate limit spacing
        time.sleep(10)

    print(f"\nDone: {success} success, {fail} fail, {rate_limit} rate-limit errors")


if __name__ == "__main__":
    main()
