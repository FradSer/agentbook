#!/usr/bin/env python
"""Build the A/B benchmark: real SWE-bench Verified instances Haiku 4.5 may fail.

The tasks are real GitHub issues (no training-data shortcut) living in large
unfamiliar codebases, and -- as in real SWE-bench -- the grading test is never
placed in the agent's workspace, so there is no test oracle to iterate against.
This isolates the question the experiment exists to answer: does agentbook's
recorded knowledge help a coding agent on tasks it genuinely cannot solve on its
own?

Substrate: SWE-bench Verified instances across multiple Python repos, modern
enough to run from source under one Python 3.10 venv, no Docker.

For each instance:
  tasks/<id>/repo/    source at base_commit, as a fresh single-commit git repo
                      (no upstream history -> no fix-commit leakage)
  tasks/<id>/BUG.md   the GitHub issue text (problem_statement) -- the symptom
  tasks/<id>/META.json
  _oracle/<id>/test.patch, gold.patch   never shown to the agent

Each task is RED-verified: FAIL_TO_PASS must fail on base+test_patch and pass
once the gold patch is applied. Only verified tasks enter manifest.json.

Run:  uv run --with pandas --with pyarrow \
          python experiments/agentbook-ab/build_benchmark.py
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "_data" / "verified.parquet"
REPO_DIR = ROOT / "_repo"
VENV_PY = ROOT / ".venv" / "bin" / "python"
TASKS = ROOT / "tasks"
ORACLE = ROOT / "_oracle"
VERIFY = ROOT / "_verify"
TIMEOUT = 600

# Repos included in the benchmark, with their version filters.
REPOS = {
    "sympy/sympy": {
        "versions": {
            "1.0",
            "1.1",
            "1.2",
            "1.4",
            "1.5",
            "1.6",
            "1.7",
            "1.8",
            "1.9",
            "1.10",
            "1.11",
            "1.12",
        }
    },
}


def sh(cmd, cwd=None, timeout=TIMEOUT, shell=False):
    return subprocess.run(
        cmd, cwd=cwd, shell=shell, capture_output=True, text=True, timeout=timeout
    )


def load_rows() -> list[dict]:
    import pandas as pd

    df = pd.read_parquet(DATA)
    masks = []
    for repo, cfg in REPOS.items():
        masks.append((df["repo"] == repo) & (df["version"].isin(cfg["versions"])))
    mask = masks[0]
    for m in masks[1:]:
        mask = mask | m
    df = df[mask]
    return df.sort_values(["repo", "instance_id"]).to_dict("records")


def patched_files(patch: str) -> list[str]:
    """Files a unified diff touches, from its `+++ b/<path>` headers."""
    return [m.group(1) for m in re.finditer(r"^\+\+\+ b/(.+)$", patch, re.M)]


def resolve_nodes(
    workspace: Path, test_files: list[str], names: list[str], test_patch: str = ""
) -> list[str]:
    """Map each FAIL_TO_PASS name to a `path::name` pytest node id.

    Searches both the base workspace and the test_patch text, since some
    FAIL_TO_PASS tests are NEW functions added by test_patch itself and won't
    exist in base. For multi-file test_patch tasks this matters: a wrong
    test_files[0] fallback yields a non-existent node and pytest errors.
    """
    # Parse test_patch to learn which test_file contains which `+def test_<name>` line.
    patch_owner: dict[str, str] = {}
    if test_patch:
        current_file: str | None = None
        for line in test_patch.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[len("+++ b/") :]
            elif current_file and re.match(r"^\+\s*def\s+(\w+)\b", line):
                m = re.match(r"^\+\s*def\s+(\w+)\b", line)
                if m:
                    patch_owner.setdefault(m.group(1), current_file)

    nodes = []
    for name in names:
        if "::" in name:
            nodes.append(name)
            continue
        hit = None
        # Prefer base-workspace match (existing test extended by test_patch).
        for tf in test_files:
            src = workspace / tf
            if src.exists() and re.search(
                rf"^\s*def {re.escape(name)}\b", src.read_text(), re.M
            ):
                hit = tf
                break
        # Then test_patch additions (new tests).
        if hit is None and name in patch_owner:
            hit = patch_owner[name]
        nodes.append(
            f"{hit}::{name}"
            if hit
            else (f"{test_files[0]}::{name}" if test_files else name)
        )
    return nodes


def repo_path(repo: str) -> Path:
    """Local clone path for a given repo slug."""
    return REPO_DIR / repo.split("/")[-1]


def make_workspace(repo: str, base_commit: str, dest: Path) -> None:
    """Snapshot repo at base_commit into `dest` as a fresh single-commit repo."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    src = repo_path(repo)
    r = sh(f"git -C {src} archive {base_commit} | tar -x -C {dest}", shell=True)
    if r.returncode != 0:
        raise RuntimeError(f"archive failed: {r.stderr}")
    sh(["git", "init", "-q"], cwd=dest)
    sh(["git", "config", "user.email", "bench@local"], cwd=dest)
    sh(["git", "config", "user.name", "bench"], cwd=dest)
    sh(["git", "add", "-A"], cwd=dest)
    sh(["git", "commit", "-q", "-m", "base"], cwd=dest)


def run_f2p(workspace: Path, nodes: list[str]) -> tuple[bool, str]:
    r = sh(
        [
            str(VENV_PY),
            "-m",
            "pytest",
            *nodes,
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=workspace,
    )
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    return r.returncode == 0, tail


def red_verify(task_dir: Path, test_patch: str, gold: str, nodes: list[str]) -> dict:
    """A task is well-formed iff F2P fails on base+test_patch and passes +gold."""
    if VERIFY.exists():
        shutil.rmtree(VERIFY)
    # Copy source files only (skip .git to avoid object-store race conditions);
    # re-init a fresh repo so git apply works cleanly.
    shutil.copytree(
        task_dir / "repo", VERIFY, ignore=shutil.ignore_patterns(".git", "__pycache__")
    )
    sh(["git", "init", "-q"], cwd=VERIFY)
    sh(["git", "config", "user.email", "bench@local"], cwd=VERIFY)
    sh(["git", "config", "user.name", "bench"], cwd=VERIFY)
    sh(["git", "add", "-A"], cwd=VERIFY)
    sh(["git", "commit", "-q", "-m", "base"], cwd=VERIFY)
    (VERIFY / "_t.patch").write_text(test_patch)
    ap_test = sh(["git", "apply", "_t.patch"], cwd=VERIFY)
    if ap_test.returncode != 0:
        return {
            "ok": False,
            "reason": f"test_patch did not apply: {ap_test.stderr.strip()}",
        }
    red_pass, red_tail = run_f2p(VERIFY, nodes)
    if red_pass:
        return {"ok": False, "reason": f"not RED (F2P already passes: {red_tail})"}
    (VERIFY / "_g.patch").write_text(gold)
    ap_gold = sh(["git", "apply", "_g.patch"], cwd=VERIFY)
    if ap_gold.returncode != 0:
        return {"ok": False, "reason": f"gold did not apply: {ap_gold.stderr.strip()}"}
    green_pass, green_tail = run_f2p(VERIFY, nodes)
    shutil.rmtree(VERIFY)
    if not green_pass:
        return {"ok": False, "reason": f"gold did not turn F2P green ({green_tail})"}
    return {"ok": True, "red_tail": red_tail, "green_tail": green_tail}


def main() -> None:
    rows = load_rows()
    repo_summary = ", ".join(
        f"{r} ({len([x for x in rows if x['repo'] == r])})" for r in REPOS
    )
    print(f"selected {len(rows)} instances across repos: {repo_summary}\n")
    TASKS.mkdir(exist_ok=True)
    ORACLE.mkdir(exist_ok=True)

    manifest = []
    for i, row in enumerate(rows, 1):
        iid = row["instance_id"]
        repo = row["repo"]
        f2p = json.loads(row["FAIL_TO_PASS"])
        p2p = json.loads(row["PASS_TO_PASS"])
        tfiles = patched_files(row["test_patch"])
        task_dir = TASKS / iid
        # Keep tasks already built and verified -- do not re-archive (score.py
        # restores the pristine base from tasks/<id>/repo, so it must be stable).
        meta_path = task_dir / "META.json"
        if meta_path.exists() and (task_dir / "repo").is_dir():
            old = json.loads(meta_path.read_text())
            if old.get("verified"):
                manifest.append(
                    {
                        "instance_id": iid,
                        "repo": old["repo"],
                        "version": old["version"],
                        "difficulty": old["difficulty"],
                    }
                )
                print(f"[{i}/{len(rows)}] {iid} ... KEEP (already verified)")
                continue
        task_dir.mkdir(exist_ok=True)
        print(
            f"[{i}/{len(rows)}] {iid} ({repo} v{row['version']}, {row['difficulty']}) ... ",
            end="",
            flush=True,
        )
        try:
            make_workspace(repo, row["base_commit"], task_dir / "repo")
            nodes = resolve_nodes(task_dir / "repo", tfiles, f2p, row["test_patch"])
            odir = ORACLE / iid
            odir.mkdir(exist_ok=True)
            (odir / "test.patch").write_text(row["test_patch"])
            (odir / "gold.patch").write_text(row["patch"])
            verdict = red_verify(task_dir, row["test_patch"], row["patch"], nodes)
        except Exception as exc:  # noqa: BLE001
            verdict = {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}

        repo_name = repo.split("/")[-1]
        (task_dir / "BUG.md").write_text(
            f"# {iid}\n\n{row['problem_statement']}\n\n"
            f"---\nFix the bug in the {repo_name} source. Do not edit any test file.\n"
        )
        meta = {
            "instance_id": iid,
            "repo": row["repo"],
            "version": str(row["version"]),
            "base_commit": row["base_commit"],
            "difficulty": row["difficulty"],
            "test_files": tfiles,
            "fail_to_pass": nodes,
            "pass_to_pass": p2p,
            "gold_files": patched_files(row["patch"]),
            "verified": verdict["ok"],
            "verdict": verdict,
        }
        (task_dir / "META.json").write_text(json.dumps(meta, indent=2) + "\n")
        if verdict["ok"]:
            manifest.append(
                {
                    "instance_id": iid,
                    "repo": row["repo"],
                    "version": str(row["version"]),
                    "difficulty": row["difficulty"],
                }
            )
            print("OK (RED verified)")
        else:
            shutil.rmtree(task_dir / "repo", ignore_errors=True)
            print(f"DROP -- {verdict['reason']}")

    (TASKS / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"\n{len(manifest)}/{len(rows)} tasks RED-verified -> {TASKS / 'manifest.json'}"
    )
    for e in manifest:
        repo_short = e.get("repo", "").split("/")[-1]
        print(
            f"  {e['instance_id']:35s} [{repo_short:15s}] v{e['version']:5s} {e['difficulty']}"
        )


if __name__ == "__main__":
    main()
