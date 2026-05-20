#!/usr/bin/env python
"""Remove stale / invalid A/B experiment artifacts.

Keeps: verified tasks (manifest.json), _oracle patches, hand corpus, core scripts.

Run:
  uv run python experiments/agentbook-ab/cleanup_experiment.py
  uv run python experiments/agentbook-ab/cleanup_experiment.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
TASKS = ROOT / "tasks"
ORACLE = ROOT / "_oracle"
MANIFEST = TASKS / "manifest.json"

# Generated per-run (recreated by benchmark pipeline + API seed)
GENERATED_GLOBS = [
    "runs",
    "runs.*",
    "prompts.*.json",
    "prompts.json",
    "short_prompts.json",
    "cells*.json",
    "results*.json",
    "recall_simulation.json",
    "*_results.json",
    "openrouter_*.log",
    "openrouter_*_results.json",
    "cells_api_errors.json",
    "corpus.seed.*.json",
    "manifest.sympy-*.json",
    "recalls/",
]

PROBE_DIRS = ["_probe", "_verify"]


def load_manifest_ids() -> set[str]:
    return {e["instance_id"] for e in json.loads(MANIFEST.read_text())}


def unverified_task_dirs(manifest_ids: set[str]) -> list[Path]:
    drop = []
    for meta in TASKS.glob("*/META.json"):
        if meta.parent.name.startswith("_"):
            continue
        iid = meta.parent.name
        if iid in manifest_ids:
            continue
        m = json.loads(meta.read_text())
        if not m.get("verified", False):
            drop.append(meta.parent)
    return drop


def rm_path(path: Path, dry_run: bool) -> None:
    if not path.exists():
        return
    label = "would remove" if dry_run else "removed"
    if path.is_dir():
        if dry_run:
            print(f"  {label} dir  {path}/")
        else:
            shutil.rmtree(path)
            print(f"  {label} dir  {path}/")
    else:
        if dry_run:
            print(f"  {label} file {path}")
        else:
            path.unlink()
            print(f"  {label} file {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Clean inappropriate A/B experiment artifacts")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-runs", action="store_true", help="Do not delete runs/")
    args = ap.parse_args()

    manifest_ids = load_manifest_ids()
    print(f"manifest: {len(manifest_ids)} verified tasks\n")

    run_globs = ("runs", "runs.*")
    if not args.keep_runs:
        print("run workspaces:")
        for pat in run_globs:
            for p in ROOT.glob(pat):
                if p.is_dir():
                    rm_path(p, args.dry_run)

    print("\ngenerated artifacts:")
    for pat in GENERATED_GLOBS:
        if args.keep_runs and pat in run_globs:
            continue
        for p in ROOT.glob(pat):
            rm_path(p, args.dry_run)

    print("\nunverified task dirs (failed RED):")
    for d in unverified_task_dirs(manifest_ids):
        odir = ORACLE / d.name
        rm_path(d, args.dry_run)
        if odir.exists():
            rm_path(odir, args.dry_run)

    print("\nprobe dirs:")
    for name in PROBE_DIRS:
        rm_path(ROOT / name, args.dry_run)

    print("\nDone." if not args.dry_run else "\nDry run complete.")


if __name__ == "__main__":
    main()
