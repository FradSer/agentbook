#!/usr/bin/env python
"""Probe which SWE-bench Verified repos pass RED-verify on the no-Docker substrate.

Uses the same venv + build_benchmark.red_verify as the sympy pilot. Prints a
summary table to stdout; does not modify manifest.json.

Run (after fetch_verified.py, clone_repos.py, bench venv setup):
  uv run --with pandas --with pyarrow python experiments/agentbook-ab/probe_substrate.py
  uv run --with pandas --with pyarrow python experiments/agentbook-ab/probe_substrate.py --repo sympy/sympy --limit 10
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import build_benchmark as bb  # noqa: E402

DATA = ROOT / "_data" / "verified.parquet"
PROBE_ROOT = ROOT / "tasks" / "_substrate_probe"


def probe_row(row: dict) -> tuple[bool, str]:
    iid = row["instance_id"]
    repo = row["repo"]
    src = bb.repo_path(repo)
    if not src.is_dir():
        return False, "repo not cloned"
    task_dir = PROBE_ROOT / iid
    if task_dir.exists():
        shutil.rmtree(task_dir)
    task_dir.mkdir(parents=True)
    try:
        bb.make_workspace(repo, row["base_commit"], task_dir / "repo")
        tfiles = bb.patched_files(row["test_patch"])
        f2p = json.loads(row["FAIL_TO_PASS"])
        nodes = bb.resolve_nodes(task_dir / "repo", tfiles, f2p, row["test_patch"])
        v = bb.red_verify(task_dir, row["test_patch"], row["patch"], nodes)
        return v.get("ok", False), v.get("reason", "ok" if v.get("ok") else "?")
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        shutil.rmtree(task_dir, ignore_errors=True)


def main() -> None:
    import pandas as pd

    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", help="Only probe this repo slug")
    ap.add_argument("--limit", type=int, default=0, help="Max instances per repo (0=all)")
    args = ap.parse_args()

    if not DATA.exists():
        raise SystemExit(f"Missing {DATA}; run fetch_verified.py")

    df = pd.read_parquet(DATA)
    if args.repo:
        df = df[df["repo"] == args.repo]
    repos = sorted(df["repo"].unique())
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"ok": 0, "fail": 0})
    reasons: dict[str, list[str]] = defaultdict(list)

    for repo in repos:
        sub = df[df["repo"] == repo]
        if args.limit:
            sub = sub.head(args.limit)
        for _, row in sub.iterrows():
            ok, reason = probe_row(row.to_dict())
            if ok:
                stats[repo]["ok"] += 1
            else:
                stats[repo]["fail"] += 1
                if len(reasons[repo]) < 3:
                    reasons[repo].append(f"{row['instance_id']}: {reason[:60]}")

    print(f"{'repo':30s} {'ok':>5s} {'fail':>5s} {'rate':>7s}")
    print("-" * 52)
    total_ok = total = 0
    for repo in repos:
        o, f = stats[repo]["ok"], stats[repo]["fail"]
        t = o + f
        total_ok += o
        total += t
        rate = f"{100 * o / t:.0f}%" if t else "n/a"
        print(f"{repo:30s} {o:5d} {f:5d} {rate:>7s}")
        for sample in reasons[repo]:
            print(f"    e.g. {sample}")
    print("-" * 52)
    print(f"{'TOTAL':30s} {total_ok:5d} {total - total_ok:5d} {100*total_ok/total:.0f}%" if total else "")

    if PROBE_ROOT.exists():
        shutil.rmtree(PROBE_ROOT, ignore_errors=True)


if __name__ == "__main__":
    main()
