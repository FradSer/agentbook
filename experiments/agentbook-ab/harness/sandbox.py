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


def _flex_locate(hay: list[str], needle: list[str]) -> int | None:
    """Index where `needle` matches `hay` ignoring per-line leading/trailing
    whitespace (the common weak-model failure mode). Returns start or None.
    Exact-strip equality only -- no fuzzy/semantic matching, so it never edits
    the wrong region."""
    n = len(needle)
    if n == 0:
        return None
    target = [ln.strip() for ln in needle]
    for i in range(len(hay) - n + 1):
        if [hay[i + j].strip() for j in range(n)] == target:
            return i
    return None


def _reindent(replace_lines: list[str], delta: int) -> list[str]:
    """Shift every non-blank replacement line by `delta` spaces (the indent gap
    between the matched site and the model's SEARCH block)."""
    out: list[str] = []
    for ln in replace_lines:
        if not ln.strip():
            out.append("")
        elif delta >= 0:
            out.append(" " * delta + ln)
        else:
            strip_n = min(-delta, len(ln) - len(ln.lstrip(" ")))
            out.append(ln[strip_n:])
    return out


def apply_search_replace(
    repo: Path, edits: list[tuple[str, str, str]]
) -> tuple[bool, str]:
    """Apply structured SEARCH/REPLACE edits, whitespace-tolerant. Returns
    (ok, msg). Moves the brittle 'reproduce exact indentation' burden off the
    weak model and onto the harness -- the fuzzy structured-edit path."""
    if not edits:
        return False, "no SEARCH/REPLACE pairs parsed"
    applied = 0
    for path, search, replace in edits:
        rel = path.lstrip("./")
        if "/tests/" in f"/{rel}" or Path(rel).name.startswith("test_"):
            return False, f"refusing to edit a test file: {rel}"
        target = repo / rel
        if not target.exists():
            return False, f"file not found: {rel}"
        text = target.read_text(errors="replace")
        search_norm = search.rstrip("\n")
        replace_norm = replace.rstrip("\n")

        # 1. exact substring replace (preserves everything verbatim)
        if search_norm and search_norm in text:
            target.write_text(text.replace(search_norm, replace_norm, 1))
            applied += 1
            continue

        # 2. whitespace-tolerant line-block match
        hay = text.splitlines()
        needle = search_norm.splitlines()
        start = _flex_locate(hay, needle)
        if start is None:
            return False, f"SEARCH block not found in {rel}"
        base_match = len(hay[start]) - len(hay[start].lstrip(" "))
        base_needle = len(needle[0]) - len(needle[0].lstrip(" "))
        new_lines = _reindent(replace_norm.splitlines(), base_match - base_needle)
        hay[start : start + len(needle)] = new_lines
        trailing = "\n" if text.endswith("\n") else ""
        target.write_text("\n".join(hay) + trailing)
        applied += 1
    return True, f"applied {applied} edit(s)"


def run_verification(
    repo: Path,
    command: str,
    expected: str | None,
    buggy: str | None,
    *,
    timeout: int = 60,
) -> tuple[bool, str]:
    """Run a public repro check and judge PASS deterministically (good_loop).

    PASS iff the post-fix marker is present AND the buggy marker is absent. This
    dual condition handles both "wrong value -> right value" checks and "noisy
    comment disappears" checks where the right value is present in both states.
    Falls back to exit-code==0 when no markers are given. This is the PUBLIC
    bug-report repro, never the held-out grading test, so using it to drive the
    model's retry loop does not leak the grade."""
    stdout, stderr, rc = run_bash(repo, command, timeout=timeout)
    out = f"{stdout}\n{stderr}"
    if not expected and not buggy:
        passed = rc == 0
    else:
        passed = True
        if expected:
            passed = passed and (expected in out)
        if buggy:
            passed = passed and (buggy not in out)
    return passed, (stdout + stderr)[-1500:]


def git_checkpoint(repo: Path, label: str) -> str | None:
    """Commit the current tree as a checkpoint; return its commit hash or None."""
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, timeout=60)
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    if not status:
        return None
    subprocess.run(
        ["git", "commit", "-q", "-m", label], cwd=repo, capture_output=True, timeout=60
    )
    r = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    )
    return r.stdout.strip() or None


def git_reset_to(repo: Path, commit: str) -> None:
    """Hard-reset the working tree to a prior checkpoint (rollback)."""
    subprocess.run(["git", "reset", "--hard", commit], cwd=repo, capture_output=True)
    subprocess.run(["git", "clean", "-fd"], cwd=repo, capture_output=True)


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
