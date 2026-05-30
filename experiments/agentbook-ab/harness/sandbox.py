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


def _locate_block(hay: list[str], needle: list[str]) -> tuple[int, int] | None:
    """Return the hay span (start, end_exclusive) matching `needle`, or None.

    Tries strict strip-equality first (`_flex_locate`), then a blank-line-
    insensitive match: the needle's non-blank stripped lines must appear as a
    contiguous run of hay's non-blank lines, with blank lines interleaved in hay
    absorbed into the span. Weak models routinely drop or insert blank lines in
    their SEARCH block; exact-count matching breaks on that. Content must still
    match exactly (modulo whitespace), so it never edits the wrong region."""
    n = len(needle)
    if n == 0:
        return None
    strict = _flex_locate(hay, needle)
    if strict is not None:
        return strict, strict + n
    nb = [ln.strip() for ln in needle if ln.strip()]
    if not nb:
        return None
    for i in range(len(hay)):
        if hay[i].strip() != nb[0]:
            continue
        ni, j = 1, i + 1
        while ni < len(nb) and j < len(hay):
            hs = hay[j].strip()
            if hs == "":
                j += 1  # absorb interleaved blank lines in the file
                continue
            if hs == nb[ni]:
                ni += 1
                j += 1
            else:
                break
        if ni == len(nb):
            return i, j
    return None


def search_not_found_hint(
    repo: Path, edits: list[tuple[str, str, str]], *, context: int = 2
) -> str:
    """Feedback for a failed SEARCH: echo the ACTUAL file lines around the
    model's best-matching anchor so it copies real text instead of re-emitting
    the same wrong SEARCH (the failed-apply doom-loop). Returns '' when there is
    nothing useful to add."""
    if not edits:
        return ""
    path, search, _ = edits[0]
    rel = path.lstrip("./")
    target = repo / rel
    if not target.exists():
        return ""
    hay = target.read_text(errors="replace").splitlines()
    needle_nb = [ln.strip() for ln in search.splitlines() if ln.strip()]
    if not needle_nb:
        return ""
    # Anchor on the needle line that appears in the file and is most distinctive
    # (fewest occurrences, then longest) -- the model usually has one real line.
    best = None  # (occurrences, -length, first_index)
    for nl in needle_nb:
        idxs = [k for k, hl in enumerate(hay) if hl.strip() == nl]
        if idxs:
            cand = (len(idxs), -len(nl), idxs[0])
            best = cand if best is None or cand < best else best
    if best is None:
        return (
            f"None of your SEARCH lines exist in {rel}. Re-read the file first "
            f"(e.g. `sed -n '1,80p' {rel}`) and copy lines verbatim before editing."
        )
    anchor = best[2]
    lo = max(0, anchor - context)
    hi = min(len(hay), anchor + len(needle_nb) + context)
    region = "\n".join(f"{k + 1}: {hay[k]}" for k in range(lo, hi))[:1200]
    return (
        f"Your SEARCH text was not found in {rel}. The ACTUAL current content "
        f"around your target (lines {lo + 1}-{hi}) is:\n```\n{region}\n```\n"
        f"Copy these lines EXACTLY (verbatim) into a new ```edit SEARCH block, "
        f"changing only what the fix requires."
    )


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

        # 2. whitespace- and blank-line-tolerant line-block match
        hay = text.splitlines()
        needle = search_norm.splitlines()
        span = _locate_block(hay, needle)
        if span is None:
            return False, f"SEARCH block not found in {rel}"
        start, end = span
        match_line = next(
            (hay[k] for k in range(start, end) if hay[k].strip()), hay[start]
        )
        needle_first = next((ln for ln in needle if ln.strip()), needle[0])
        base_match = len(match_line) - len(match_line.lstrip(" "))
        base_needle = len(needle_first) - len(needle_first.lstrip(" "))
        new_lines = _reindent(replace_norm.splitlines(), base_match - base_needle)
        hay[start:end] = new_lines
        trailing = "\n" if text.endswith("\n") else ""
        target.write_text("\n".join(hay) + trailing)
        applied += 1
    return True, f"applied {applied} edit(s)"


def _any_in(needle, hay: str) -> bool:
    """True if `needle` (str or list of strs) has any occurrence in `hay`."""
    if isinstance(needle, list):
        return any(n in hay for n in needle if n)
    return bool(needle) and needle in hay


def run_verification(
    repo: Path,
    command: str,
    expected,
    buggy,
    *,
    timeout: int = 60,
) -> tuple[bool, str]:
    """Run a public repro check and judge PASS deterministically (good_loop).

    PASS iff a post-fix marker is present AND the buggy marker is absent. Both
    `expected` and `buggy` may be a single substring or a list of alternatives
    (any-of). This handles both "wrong value -> right value" checks and "noisy
    comment disappears" checks where the right value is present in both states.
    Falls back to exit-code==0 when no markers are given. The repro is the
    PUBLIC bug-report repro, never the held-out grading test."""
    stdout, stderr, rc = run_bash(repo, command, timeout=timeout)
    out = f"{stdout}\n{stderr}"
    if not expected and not buggy:
        passed = rc == 0
    else:
        passed = True
        if expected:
            passed = passed and _any_in(expected, out)
        if buggy:
            passed = passed and not _any_in(buggy, out)
    return passed, (stdout + stderr)[-1500:]


def run_verifications(
    repo: Path, repros: list[dict], *, timeout: int = 60
) -> tuple[bool, str]:
    """Run a LIST of public repros; PASS iff every one passes. Forces multi-site
    fixes by under-specifying each repro to one site/case (one per cue). Returns
    (all_passed, log_tail)."""
    if not repros:
        return False, "no repros configured"
    all_passed = True
    lines: list[str] = []
    for v in repros:
        passed, out = run_verification(
            repo,
            v["command"],
            v.get("expected"),
            v.get("buggy"),
            timeout=timeout,
        )
        all_passed = all_passed and passed
        label = (v.get("label") or v["command"])[:60]
        tail = next(
            (ln for ln in reversed((out or "").splitlines()) if ln.strip()), ""
        )[:120]
        lines.append(f"  [{'PASS' if passed else 'FAIL'}] {label}  -> {tail}")
    return all_passed, "\n".join(lines)[-2000:]


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
