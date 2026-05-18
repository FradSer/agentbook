#!/usr/bin/env python
"""Independently score the A/B runs.

Ground truth is computed here, not trusted from the sub-agents. For every
run workspace the grading test is reconstituted from scratch:

  1. every test file the agent could have touched is restored from the
     pristine base in tasks/<id>/repo/  (defeats test tampering);
  2. the held-out test_patch is applied on top of the agent's source edits;
  3. the FAIL_TO_PASS node ids are run with the pinned venv pytest.

A run passes iff every FAIL_TO_PASS test is green. Source-diff size is measured
against the pristine base, excluding test files.

Run:  uv run python experiments/agentbook-ab/score.py [arm ...]
      (default arms: control good bad -- whichever runs/ dirs exist)
"""

from __future__ import annotations

import difflib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
TASKS = ROOT / "tasks"
ORACLE = ROOT / "_oracle"
RUNS = ROOT / "runs"
VENV_PY = ROOT / ".venv" / "bin" / "python"
DEFAULT_ARMS = ("control", "good", "bad")


def sh(cmd, cwd=None, timeout=600):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def diff_lines(base_repo: Path, run_repo: Path, exclude: set[str]) -> int:
    """Lines changed in non-test source files, run vs pristine base."""
    total = 0
    for gold in sorted(p for p in base_repo.rglob("*.py")):
        rel = gold.relative_to(base_repo).as_posix()
        if rel in exclude:
            continue
        cand = run_repo / rel
        if not cand.exists():
            continue
        a = gold.read_text(errors="replace").splitlines()
        b = cand.read_text(errors="replace").splitlines()
        d = difflib.unified_diff(a, b, lineterm="", n=0)
        total += sum(
            1 for ln in d if ln[:1] in "+-" and not ln.startswith(("+++", "---"))
        )
    return total


def score_run(meta: dict, arm: str) -> dict:
    iid = meta["instance_id"]
    base_repo = TASKS / iid / "repo"
    run_repo = RUNS / f"{iid}__{arm}" / "repo"
    test_files = meta["test_files"]

    # 0. restore working tree to committed HEAD so prior scoring runs cannot
    #    leak test_patch (or any other) edits into this one. The committed
    #    state is exactly what we want to grade against.
    sh(["git", "reset", "--hard", "HEAD"], cwd=run_repo)
    sh(["git", "clean", "-fd"], cwd=run_repo)

    # 1. restore every test file from pristine base
    for tf in test_files:
        src = base_repo / tf
        dst = run_repo / tf
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copy2(src, dst)

    # 2. apply the held-out grading test_patch
    patch = (ORACLE / iid / "test.patch").read_text()
    (run_repo / "_score_t.patch").write_text(patch)
    ap = sh(["git", "apply", "--include=*", "_score_t.patch"], cwd=run_repo)
    (run_repo / "_score_t.patch").unlink(missing_ok=True)
    if ap.returncode != 0:
        return {
            "instance_id": iid,
            "arm": arm,
            "tests_pass": False,
            "diff_lines": -1,
            "summary": f"test_patch apply failed: {ap.stderr.strip()[:200]}",
        }

    # 3. run FAIL_TO_PASS (a hung test from a bad fix counts as FAIL)
    cmd = [
        str(VENV_PY),
        "-m",
        "pytest",
        *meta["fail_to_pass"],
        "-q",
        "--no-header",
        "-p",
        "no:cacheprovider",
    ]
    try:
        r = sh(cmd, cwd=run_repo, timeout=180)
        passed = r.returncode == 0
        tail = (r.stdout.strip().splitlines() or [""])[-1]
    except subprocess.TimeoutExpired:
        passed = False
        tail = "TIMEOUT (>180s) -- treated as FAIL"
    return {
        "instance_id": iid,
        "arm": arm,
        "tests_pass": passed,
        "diff_lines": diff_lines(base_repo, run_repo, set(test_files)),
        "summary": tail,
    }


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Score A/B runs against FAIL_TO_PASS tests")
    ap.add_argument(
        "arms",
        nargs="*",
        default=list(DEFAULT_ARMS),
        help=f"Arms to score (default: {' '.join(DEFAULT_ARMS)})",
    )
    ap.add_argument(
        "--manifest",
        type=Path,
        default=TASKS / "manifest.json",
        help="Task manifest (default: tasks/manifest.json; try manifest.hard.json)",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Results JSON (default: results.json, or results.hard.json if manifest is hard)",
    )
    args = ap.parse_args()
    out_path = args.output
    if out_path is None:
        manifest_name = args.manifest.resolve().name
        if manifest_name.startswith("manifest.hard"):
            out_path = ROOT / "results.hard.json"
        elif manifest_name.startswith("manifest.complex"):
            out_path = ROOT / "results.complex.json"
        elif manifest_name.startswith("manifest.responsible"):
            out_path = ROOT / "results.responsible.json"
        elif "eval-v2" in manifest_name or manifest_name.startswith("manifest.eval"):
            out_path = ROOT / "results.eval-v2.json"
        elif manifest_name.startswith("manifest.full"):
            out_path = ROOT / "results.full.json"
        else:
            out_path = ROOT / "results.json"
    arms = [a for a in args.arms if (RUNS).exists()]
    arms = [a for a in arms if any(RUNS.glob(f"*__{a}"))]
    manifest = json.loads(args.manifest.read_text())
    metas = {
        e["instance_id"]: json.loads(
            (TASKS / e["instance_id"] / "META.json").read_text()
        )
        for e in manifest
    }

    results = []
    for iid, meta in metas.items():
        for arm in arms:
            if (RUNS / f"{iid}__{arm}").is_dir():
                print(f"scoring {iid} [{arm}] ...", flush=True)
                results.append(score_run(meta, arm))
    out_path.write_text(json.dumps(results, indent=2) + "\n")

    by = {(r["instance_id"], r["arm"]): r for r in results}
    print(f"\n{'instance':30s}" + "".join(f"{a:>14s}" for a in arms))
    print("-" * (30 + 14 * len(arms)))
    agg = {a: [0, 0] for a in arms}
    for iid in metas:
        cells = []
        for arm in arms:
            r = by.get((iid, arm))
            if r is None:
                cells.append(f"{'-':>14s}")
                continue
            agg[arm][1] += 1
            agg[arm][0] += int(r["tests_pass"])
            mark = "PASS" if r["tests_pass"] else "FAIL"
            cells.append(f"{mark} d{r['diff_lines']:<3d}".rjust(14))
        print(f"{iid:30s}" + "".join(cells))
    print("-" * (30 + 14 * len(arms)))
    for arm in arms:
        p, t = agg[arm]
        print(f"  {arm:10s} pass@1 = {p}/{t}")
    print(f"\nresults -> {out_path}")


if __name__ == "__main__":
    main()
