#!/usr/bin/env python
"""Prepare a pristine git workspace for one A/B cell."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
TASKS = ROOT / "tasks"
RUNS = ROOT / "runs"


def has_agent_fix(repo: Path) -> bool:
    """True if repo has any commit after the initial base commit."""
    if not repo.is_dir():
        return False
    log = subprocess.run(
        ["git", "log", "--format=%s"],
        cwd=repo,
        capture_output=True,
        text=True,
    ).stdout.strip().splitlines()
    for line in log:
        if line.lower().startswith("base"):
            continue
        return True
    return False


def prepare_run_dir(iid: str, arm: str, *, runs_dir: Path | None = None) -> Path:
    """Copy task repo into runs/<id>__<arm>/repo and create a base commit."""
    runs = runs_dir or RUNS
    run_dir = runs / f"{iid}__{arm}"
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
