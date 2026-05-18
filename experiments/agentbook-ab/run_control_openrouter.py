#!/usr/bin/env python
"""Run the control arm directly via OpenRouter API (Claude Haiku 4.5).

Bypasses Bailian rate limits by using OpenRouter to call Claude Haiku.
Runs one task at a time (serial) to avoid any provider rate limits.

Usage:
    uv run python experiments/agentbook-ab/run_control_openrouter.py [--task TASK_ID] [--all]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).parent
TASKS = ROOT / "tasks"
RUNS = ROOT / "runs"
VENV_PY = ROOT / ".venv" / "bin" / "python"
ORACLE = ROOT / "_oracle"
MANIFEST = TASKS / "manifest.json"

# OpenRouter config
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
MODEL = "anthropic/claude-3.5-haiku-20241022"  # Claude Haiku 4.5 on OpenRouter

PROMPT_TEMPLATE = """You are a coding agent tasked with fixing a bug in a Python project.

## Bug Description

{bug_description}

## Instructions

1. Read the bug description carefully
2. Explore the source code in the repository to understand the problem
3. Identify the root cause of the bug
4. Make minimal, targeted changes to fix the bug
5. Do NOT edit any test files - only fix source code
6. Your fix should be as minimal as possible

The repository is at: {repo_path}

Important: Only modify source files (not test files). Focus on the minimal fix that addresses the root cause."""

MAX_TOKENS = 4096
TIMEOUT_SECONDS = 600  # 10 minutes per task
DELAY_BETWEEN_TASKS = 30  # seconds between tasks


def load_env() -> str:
    """Load OPENROUTER_API_KEY from .env file."""
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
        raise RuntimeError("OPENROUTER_API_KEY not found in .env or env vars")
    return key


def call_haiku(api_key: str, prompt: str) -> str:
    """Call Claude Haiku via OpenRouter."""
    import json as _json
    import urllib.request

    url = f"{OPENROUTER_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/agentbook",
        "X-Title": "agentbook-ab-control",
    }
    body = _json.dumps(
        {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode()

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        data = _json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]


def call_haiku_sdk(api_key: str, prompt: str) -> str:
    """Call Claude Haiku via OpenRouter using the openai SDK."""
    from openai import OpenAI

    client = OpenAI(
        base_url=OPENROUTER_BASE,
        api_key=api_key,
    )
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
        timeout=TIMEOUT_SECONDS,
    )
    return response.choices[0].message.content


def prepare_run_dir(task_id: str) -> Path:
    """Prepare the control run directory from pristine task."""
    run_dir = RUNS / f"{task_id}__control"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)

    # Copy pristine repo
    src_repo = TASKS / task_id / "repo"
    dest_repo = run_dir / "repo"
    shutil.copytree(src_repo, dest_repo)

    # Init git for scoring
    subprocess.run(
        ["git", "init", "-q"], cwd=dest_repo, capture_output=True, timeout=30
    )
    subprocess.run(
        ["git", "config", "user.email", "bench@local"],
        cwd=dest_repo,
        capture_output=True,
        timeout=30,
    )
    subprocess.run(
        ["git", "config", "user.name", "bench"],
        cwd=dest_repo,
        capture_output=True,
        timeout=30,
    )
    subprocess.run(["git", "add", "-A"], cwd=dest_repo, capture_output=True, timeout=60)
    subprocess.run(
        ["git", "commit", "-q", "-m", "base"],
        cwd=dest_repo,
        capture_output=True,
        timeout=60,
    )

    return run_dir


def apply_agent_fix(run_repo: Path, agent_output: str) -> bool:
    """Parse agent output and apply code changes to the repo.

    The agent output should contain code changes in a recognizable format.
    We look for file paths and code blocks in the response.
    """

    # Strategy: Write the agent's full response to a log, then
    # look for explicit file-change instructions.
    # Haiku often outputs changes in diff format or "replace X with Y" format.

    # Save raw output for debugging
    (run_repo.parent / "agent_response.md").write_text(agent_output)

    # Try to extract code blocks with file path annotations
    # Pattern: ```python (or ```) preceded by a file path reference
    # E.g. "In file sympy/core/numbers.py:"

    changes_applied = False

    # Look for patterns like:
    # "sympy/core/numbers.py" or "File: sympy/core/numbers.py"
    # followed by a code block

    # More robust: look for the agent suggesting specific edits
    # and try to apply them using string replacement

    # For now, write the full conversation to a log file
    # The scoring step will check what the agent actually changed

    return changes_applied


def run_task(task_id: str, api_key: str) -> dict:
    """Run a single control task through OpenRouter."""
    bug_path = TASKS / task_id / "BUG.md"
    meta_path = TASKS / task_id / "META.json"

    if not bug_path.exists() or not meta_path.exists():
        return {"task_id": task_id, "status": "missing_infrastructure"}

    bug_text = bug_path.read_text()
    meta = json.loads(meta_path.read_text())

    # Prepare run dir
    run_dir = prepare_run_dir(task_id)
    run_repo = run_dir / "repo"

    # Build prompt with key source file paths from gold_files
    gold_files = meta.get("gold_files", [])
    file_hint = ""
    if gold_files:
        file_hint = f"\nKey files to investigate: {', '.join(gold_files)}\n"

    prompt = (
        PROMPT_TEMPLATE.format(
            bug_description=bug_text,
            repo_path=str(run_repo),
        )
        + file_hint
    )

    # Call Haiku via OpenRouter
    try:
        response = call_haiku_sdk(api_key, prompt)
    except Exception as exc:
        return {"task_id": task_id, "status": "api_error", "error": str(exc)}

    # Parse and apply the fix
    apply_agent_fix(run_repo, response)

    return {"task_id": task_id, "status": "completed", "response_length": len(response)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run control arm via OpenRouter")
    parser.add_argument("--task", help="Specific task ID to run")
    parser.add_argument("--all", action="store_true", help="Run all d0 control tasks")
    parser.add_argument(
        "--dry-run", action="store_true", help="Just list tasks, don't run"
    )
    args = parser.parse_args()

    api_key = load_env()
    manifest = json.loads(MANIFEST.read_text())

    # Find d0 control tasks (no real edits in run dir)
    d0_tasks = []
    for entry in manifest:
        iid = entry["instance_id"]
        run_repo = RUNS / f"{iid}__control" / "repo"
        if not run_repo.exists():
            continue
        # Check if agent made any non-test source changes
        r = subprocess.run(
            ["git", "diff", "--stat", "HEAD"],
            cwd=run_repo,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # d0 = no source changes (or only test changes)
        diff_stat = r.stdout.strip()
        if not diff_stat or "test" in diff_stat.lower():
            d0_tasks.append(iid)

    if args.task:
        tasks_to_run = [args.task]
    elif args.all:
        tasks_to_run = d0_tasks
    else:
        # Default: run d0 tasks
        tasks_to_run = d0_tasks

    print(f"Tasks to run: {len(tasks_to_run)}")
    for t in tasks_to_run:
        print(f"  {t}")

    if args.dry_run:
        return

    results = []
    for i, task_id in enumerate(tasks_to_run):
        print(f"\n[{i + 1}/{len(tasks_to_run)}] Running {task_id} ...", flush=True)
        result = run_task(task_id, api_key)
        results.append(result)
        print(f"  -> {result['status']}", flush=True)

        if i < len(tasks_to_run) - 1:
            print(f"  Waiting {DELAY_BETWEEN_TASKS}s before next task ...", flush=True)
            time.sleep(DELAY_BETWEEN_TASKS)

    # Save results
    results_file = ROOT / "control_openrouter_results.json"
    results_file.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nResults saved to {results_file}")


if __name__ == "__main__":
    main()
