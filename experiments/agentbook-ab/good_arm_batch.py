#!/usr/bin/env python3
"""Apply good-arm fixes via OpenRouter using only runs/<id>__good/prompt.md."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

EXP = Path(__file__).parent
RUNS = EXP / "runs"
sys.path.insert(0, str(EXP))

import run_all_cells as rac  # noqa: E402


def changed_files(repo: Path) -> list[str]:
    r = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def has_agent_fix(repo: Path) -> bool:
    r = subprocess.run(
        ["git", "log", "--oneline", "-1"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return "agent fix" in r.stdout


def commit_agent_fix(repo: Path) -> bool:
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, timeout=60)
    st = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=repo,
        capture_output=True,
        timeout=30,
    )
    if st.returncode == 0:
        return False
    subprocess.run(
        ["git", "commit", "-m", "agent fix"],
        cwd=repo,
        capture_output=True,
        timeout=60,
    )
    return True


def reset_to_base(repo: Path) -> None:
    subprocess.run(["git", "checkout", "-q", "base"], cwd=repo, capture_output=True)
    subprocess.run(["git", "reset", "--hard", "-q", "base"], cwd=repo, capture_output=True)


def run_cell(iid: str, api_key: str) -> dict:
    run_dir = RUNS / f"{iid}__good"
    repo = run_dir / "repo"
    prompt_path = run_dir / "prompt.md"
    if not repo.is_dir() or not prompt_path.is_file():
        return {
            "instance_id": iid,
            "committed": False,
            "files_changed": [],
            "error": "missing run dir or prompt.md",
        }

    if has_agent_fix(repo):
        return {
            "instance_id": iid,
            "committed": True,
            "files_changed": changed_files(repo) or _files_from_last_commit(repo),
        }

    reset_to_base(repo)
    prompt = prompt_path.read_text()
    try:
        response = rac.call_haiku(api_key, prompt)
    except Exception as exc:  # noqa: BLE001
        return {
            "instance_id": iid,
            "committed": False,
            "files_changed": [],
            "error": str(exc),
        }

    (run_dir / "haiku_response.md").write_text(response)
    applied = False
    diff_match = re.search(r"```diff\n(.*?)```", response, re.DOTALL)
    if diff_match:
        applied = rac.apply_diff(repo, diff_match.group(1))
    if not applied:
        applied = rac.apply_diff(repo, response)
    if not applied:
        applied = rac.apply_code_blocks(repo, response)

    committed = False
    if applied:
        committed = commit_agent_fix(repo)

    files = changed_files(repo) if committed else []
    if committed and not files:
        files = _files_from_last_commit(repo)

    return {
        "instance_id": iid,
        "committed": committed,
        "files_changed": files,
    }


def _files_from_last_commit(repo: Path) -> list[str]:
    r = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def main() -> None:
    cells = [
        iid
        for iid, arm in json.loads((EXP / "cells_full.json").read_text())
        if arm == "good"
    ]
    api_key = rac.load_env()
    results = []
    for i, iid in enumerate(cells, 1):
        print(f"[{i}/{len(cells)}] {iid}", flush=True)
        results.append(run_cell(iid, api_key))
        if i < len(cells):
            time.sleep(3)
    out = EXP / "good_results.json"
    out.write_text(json.dumps(results, indent=2) + "\n")
    done = sum(1 for r in results if r.get("committed"))
    print(f"Done: {done}/{len(results)} -> {out}")


if __name__ == "__main__":
    main()
