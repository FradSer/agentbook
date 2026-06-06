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
once the gold patch is applied. Only verified tasks enter the manifest.

Run:  uv run --with pandas --with pyarrow \
          python experiments/agentbook-ab/build_benchmark.py
      uv run --with pandas --with pyarrow \
          python experiments/agentbook-ab/build_benchmark.py --multirepo
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from benchmark.repo_config import (  # noqa: E402
    MULTIREPO_PILOT,
    REPOS,
    SYMPY_ONLY,
    VENV_PY,
    install_venv_requirements,
    install_workspace,
    workspace_env,
)

DATA = ROOT / "_data" / "verified.parquet"
REPO_DIR = ROOT / "_repo"
TASKS = ROOT / "tasks"
ORACLE = ROOT / "_oracle"
VERIFY = ROOT / "_verify"
TIMEOUT = 600


def sh(cmd, cwd=None, timeout=TIMEOUT, shell=False, env=None):
    return subprocess.run(
        cmd,
        cwd=cwd,
        shell=shell,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def load_rows(repos: set[str]) -> list[dict]:
    import pandas as pd

    df = pd.read_parquet(DATA)
    masks = []
    for repo in repos:
        cfg = REPOS[repo]
        masks.append((df["repo"] == repo) & (df["version"].isin(cfg["versions"])))
    mask = masks[0]
    for m in masks[1:]:
        mask = mask | m
    df = df[mask].sort_values(["repo", "instance_id"])

    rows: list[dict] = []
    for repo in sorted(repos):
        cfg = REPOS[repo]
        sub = df[df["repo"] == repo]
        cap = cfg.get("max_instances")
        if cap is not None:
            sub = sub.head(int(cap))
        rows.extend(sub.to_dict("records"))
    return rows


def patched_files(patch: str) -> list[str]:
    """Files a unified diff touches, from its `+++ b/<path>` headers."""
    return [m.group(1) for m in re.finditer(r"^\+\+\+ b/(.+)$", patch, re.M)]


def resolve_nodes(
    workspace: Path, test_files: list[str], names: list[str], test_patch: str = ""
) -> list[str]:
    """Map each FAIL_TO_PASS name to a `path::name` pytest node id."""
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
        for tf in test_files:
            src = workspace / tf
            if src.exists() and re.search(
                rf"^\s*def {re.escape(name)}\b", src.read_text(), re.M
            ):
                hit = tf
                break
        if hit is None and name in patch_owner:
            hit = patch_owner[name]
        nodes.append(
            f"{hit}::{name}"
            if hit
            else (f"{test_files[0]}::{name}" if test_files else name)
        )
    return nodes


def repo_path(repo: str) -> Path:
    return REPO_DIR / repo.split("/")[-1]


def make_workspace(repo: str, base_commit: str, dest: Path) -> None:
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


def run_f2p(workspace: Path, nodes: list[str], *, repo: str = "") -> tuple[bool, str]:
    env = workspace_env(repo, workspace) if repo else None
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
        env=env,
    )
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    if r.returncode != 0 and r.stderr.strip():
        tail = f"{tail} | {r.stderr.strip().splitlines()[-1]}"
    return r.returncode == 0, tail


def red_verify(
    repo: str, task_dir: Path, test_patch: str, gold: str, nodes: list[str]
) -> dict:
    """A task is well-formed iff F2P fails on base+test_patch and passes +gold."""
    if VERIFY.exists():
        shutil.rmtree(VERIFY)
    shutil.copytree(
        task_dir / "repo", VERIFY, ignore=shutil.ignore_patterns(".git", "__pycache__")
    )
    sh(["git", "init", "-q"], cwd=VERIFY)
    sh(["git", "config", "user.email", "bench@local"], cwd=VERIFY)
    sh(["git", "config", "user.name", "bench"], cwd=VERIFY)
    sh(["git", "add", "-A"], cwd=VERIFY)
    sh(["git", "commit", "-q", "-m", "base"], cwd=VERIFY)

    ok, msg = install_workspace(repo, VERIFY)
    if not ok:
        shutil.rmtree(VERIFY, ignore_errors=True)
        return {"ok": False, "reason": f"workspace install failed: {msg}"}

    (VERIFY / "_t.patch").write_text(test_patch)
    ap_test = sh(["git", "apply", "_t.patch"], cwd=VERIFY)
    if ap_test.returncode != 0:
        shutil.rmtree(VERIFY, ignore_errors=True)
        return {
            "ok": False,
            "reason": f"test_patch did not apply: {ap_test.stderr.strip()}",
        }
    red_pass, red_tail = run_f2p(VERIFY, nodes, repo=repo)
    if red_pass:
        shutil.rmtree(VERIFY, ignore_errors=True)
        return {"ok": False, "reason": f"not RED (F2P already passes: {red_tail})"}
    (VERIFY / "_g.patch").write_text(gold)
    ap_gold = sh(["git", "apply", "_g.patch"], cwd=VERIFY)
    if ap_gold.returncode != 0:
        shutil.rmtree(VERIFY, ignore_errors=True)
        return {"ok": False, "reason": f"gold did not apply: {ap_gold.stderr.strip()}"}
    green_pass, green_tail = run_f2p(VERIFY, nodes, repo=repo)
    shutil.rmtree(VERIFY, ignore_errors=True)
    if not green_pass:
        return {"ok": False, "reason": f"gold did not turn F2P green ({green_tail})"}
    return {"ok": True, "red_tail": red_tail, "green_tail": green_tail}


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="RED-verify SWE-bench Verified tasks")
    ap.add_argument(
        "--rebuild-unverified",
        action="store_true",
        help="Re-run RED verify for tasks whose META.json has verified=false",
    )
    ap.add_argument(
        "--multirepo",
        action="store_true",
        help="Include sklearn + pytest pilot repos (in addition to sympy)",
    )
    ap.add_argument(
        "--repos",
        action="append",
        help="Explicit repo slugs (owner/name); overrides --multirepo default",
    )
    ap.add_argument(
        "--output-manifest",
        type=Path,
        default=None,
        help="Manifest output path (default: tasks/manifest.json)",
    )
    args = ap.parse_args()

    if args.repos:
        repos = set(args.repos)
    elif args.multirepo:
        repos = MULTIREPO_PILOT
    else:
        repos = SYMPY_ONLY

    unknown = repos - set(REPOS)
    if unknown:
        raise SystemExit(f"unknown repos: {sorted(unknown)}")

    print("Installing venv requirements for selected repos ...")
    install_venv_requirements(repos)

    rows = load_rows(repos)
    repo_summary = ", ".join(
        f"{r} ({len([x for x in rows if x['repo'] == r])})" for r in sorted(repos)
    )
    print(f"selected {len(rows)} instances across repos: {repo_summary}\n")
    TASKS.mkdir(exist_ok=True)
    ORACLE.mkdir(exist_ok=True)

    manifest: list[dict] = []
    failures: list[dict] = []

    for i, row in enumerate(rows, 1):
        iid = row["instance_id"]
        repo = row["repo"]
        f2p = json.loads(row["FAIL_TO_PASS"])
        p2p = json.loads(row["PASS_TO_PASS"])
        tfiles = patched_files(row["test_patch"])
        task_dir = TASKS / iid
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
            if not args.rebuild_unverified:
                print(
                    f"[{i}/{len(rows)}] {iid} ... SKIP (unverified, use --rebuild-unverified)"
                )
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
            verdict = red_verify(repo, task_dir, row["test_patch"], row["patch"], nodes)
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
            failures.append(
                {
                    "instance_id": iid,
                    "repo": repo,
                    "reason": verdict.get("reason", "unknown"),
                }
            )
            shutil.rmtree(task_dir / "repo", ignore_errors=True)
            print(f"DROP -- {verdict['reason']}")

    if args.multirepo or (args.repos and repos != SYMPY_ONLY):
        sympy_manifest = [e for e in manifest if e.get("repo") == "sympy/sympy"]
        (TASKS / "manifest.json").write_text(
            json.dumps(sympy_manifest, indent=2) + "\n"
        )
        print(
            f"\n{len(sympy_manifest)} sympy tasks preserved -> {TASKS / 'manifest.json'}"
        )
        from filter_manifest import control_fail_ids, preset_multirepo  # noqa: WPS433

        control_fail = control_fail_ids()
        multirepo = preset_multirepo(sympy_manifest, control_fail)
        multirepo_path = TASKS / "manifest.multirepo.json"
        multirepo_path.write_text(json.dumps(multirepo, indent=2) + "\n")
        print(
            f"{len(multirepo)} multi-repo tasks -> {multirepo_path} "
            f"(sympy hard + pilot repos)"
        )
        out_manifest = multirepo_path
    else:
        out_manifest = args.output_manifest or (TASKS / "manifest.json")
        out_manifest.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"\n{len(manifest)}/{len(rows)} tasks RED-verified -> {out_manifest}")
    report_path = ROOT / "_data" / "red_verify_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "repos": sorted(repos),
                "verified": len(manifest),
                "attempted": len(rows),
                "failures": failures,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"failure report -> {report_path}")
    for e in (
        multirepo
        if args.multirepo or (args.repos and repos != SYMPY_ONLY)
        else manifest
    ):
        repo_short = e.get("repo", "").split("/")[-1]
        print(
            f"  {e['instance_id']:35s} [{repo_short:15s}] v{e['version']:5s} {e['difficulty']}"
        )


if __name__ == "__main__":
    main()
