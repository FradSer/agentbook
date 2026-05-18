#!/usr/bin/env python
"""Export agent run workspaces to SWE-bench prediction JSONL for official evaluation.

Each line:
  {"instance_id": "...", "model_name_or_path": "<arm>", "model_patch": "<unified diff>"}

Patches are computed as `git diff base..HEAD` over non-test source files only
(test files are excluded from the patch sent to the harness; grading restores them).

Run:
  uv run python experiments/agentbook-ab/export_predictions.py \
    --arm good --model agentbook-good > predictions/good.jsonl
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
TASKS = ROOT / "tasks"
RUNS = ROOT / "runs"
MANIFEST = TASKS / "manifest.json"


def base_commit(run_repo: Path) -> str | None:
    log = subprocess.run(
        ["git", "log", "--format=%H %s"],
        cwd=run_repo,
        capture_output=True,
        text=True,
    ).stdout.strip().split("\n")
    for line in log:
        parts = line.split(maxsplit=1)
        if len(parts) == 2 and "base" in parts[1].lower():
            return parts[0]
    return None


def patch_for_run(iid: str, arm: str, test_files: set[str]) -> str | None:
    run_repo = RUNS / f"{iid}__{arm}" / "repo"
    if not run_repo.is_dir():
        return None
    base = base_commit(run_repo)
    if not base:
        return None
    r = subprocess.run(
        ["git", "diff", base, "HEAD", "--"],
        cwd=run_repo,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return None
    lines = []
    for line in r.stdout.splitlines(keepends=True):
        if line.startswith("diff --git "):
            # exclude test file paths
            parts = line.split()
            if len(parts) >= 4:
                path_b = parts[3][2:]  # b/path
                if path_b in test_files:
                    continue
            lines.append(line)
        elif lines:
            lines.append(line)
    patch = "".join(lines).strip()
    return patch or None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="good", choices=["control", "good", "bad"])
    ap.add_argument("--model", default="agentbook-ab")
    ap.add_argument("-o", "--output", type=Path, help="Write JSONL here (default stdout)")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for entry in manifest:
        iid = entry["instance_id"]
        meta = json.loads((TASKS / iid / "META.json").read_text())
        test_files = set(meta.get("test_files", []))
        patch = patch_for_run(iid, args.arm, test_files)
        if patch is None:
            continue
        rows.append(
            {
                "instance_id": iid,
                "model_name_or_path": args.model,
                "model_patch": patch,
            }
        )

    out_lines = [json.dumps(r) + "\n" for r in rows]
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("".join(out_lines))
        print(f"Wrote {len(rows)} predictions -> {args.output}", flush=True)
    else:
        for line in out_lines:
            print(line, end="")


if __name__ == "__main__":
    main()
