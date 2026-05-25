"""Per-sample workspace preparation + bash execution for the agentic loop."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cell_workspace import has_agent_fix, prepare_run_dir  # noqa: E402

RUNS_V2 = ROOT / "runs_v2"
_MAX_TAIL = 4000  # chars per stream appended to history


def cell_dirname(iid: str, arm: str, model_slug: str, sample_idx: int) -> str:
    return f"{iid}__{arm}__{model_slug}__s{sample_idx}"


def prepare_cell(iid: str, arm: str, model_slug: str, sample_idx: int) -> Path:
    """Fresh isolated repo for one cell-sample under runs_v2/. Returns repo path."""
    composite_arm = f"{arm}__{model_slug}__s{sample_idx}"
    return prepare_run_dir(iid, composite_arm, runs_dir=RUNS_V2)


def _scrub_env() -> dict[str, str]:
    """Env for the agent's bash: strip secrets, keep the venv python on PATH so
    the agent has a working `python` (with sympy+mpmath) for self-tests. Grading
    is protected separately by score.py stripping any editable import finder
    before each run, so an agent `pip install -e .` cannot corrupt the grade."""
    import os

    env = dict(os.environ)
    for key in list(env):
        up = key.upper()
        if any(s in up for s in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            env.pop(key, None)
    return env


def run_bash(repo: Path, command: str, timeout: int = 120) -> tuple[str, str, int]:
    """Execute one bash command in the repo; return (stdout, stderr, returncode)."""
    try:
        r = subprocess.run(
            ["bash", "-lc", command],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_scrub_env(),
        )
        return r.stdout[-_MAX_TAIL:], r.stderr[-_MAX_TAIL:], r.returncode
    except subprocess.TimeoutExpired:
        return "", f"command timed out after {timeout}s", 124


def apply_unified_diff(repo: Path, diff: str) -> tuple[bool, str]:
    """Apply a unified diff via `git apply` (tolerant flags). Returns (ok, msg).
    Moves the brittle 'translate intent -> exact file edit' step off the weak
    model and onto the harness."""
    (repo / "_agent.patch").write_text(diff)
    for flags in (["--3way"], ["-p1"], ["-p0"], ["--unidiff-zero"]):
        r = subprocess.run(
            ["git", "apply", *flags, "_agent.patch"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            (repo / "_agent.patch").unlink(missing_ok=True)
            return True, f"applied ({' '.join(flags)})"
    msg = r.stderr.strip()[:300]
    (repo / "_agent.patch").unlink(missing_ok=True)
    return False, f"git apply failed: {msg}"


def commit_fix(repo: Path) -> bool:
    """Commit any working-tree changes as 'agent fix'; return has_agent_fix."""
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, timeout=60)
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    if status:
        subprocess.run(
            ["git", "commit", "-q", "-m", "agent fix"],
            cwd=repo,
            capture_output=True,
            timeout=60,
        )
    return has_agent_fix(repo)
