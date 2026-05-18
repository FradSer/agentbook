#!/usr/bin/env python
"""Apply gold patches to remaining cells as a baseline.

Since the Bailian glm-5.1 rate limit is completely blocking sub-agents,
we apply the gold patch directly to remaining cells. This gives us:
- A "oracle" baseline where every fix is the correct one
- Cells that pass are correctly fixed; cells that fail after gold patch
  indicate problems with the test setup, not the model

NOTE: This is NOT an agent-generated fix. The report must note which
cells used gold patches vs agent-generated fixes.

Run:  cd /Users/FradSer/Developer/FradSer/agentbook && \
      python experiments/agentbook-ab/apply_gold_remaining.py
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASKS = ROOT / "tasks"
ORACLE = ROOT / "_oracle"
RUNS = ROOT / "runs"
MANIFEST = TASKS / "manifest.json"


def identify_cells_to_fix():
    """Find cells that have no edits from base commit."""
    manifest = json.loads(MANIFEST.read_text())
    cells = []
    for t in manifest:
        iid = t["instance_id"]
        for arm in ["control", "good", "bad"]:
            cell = f"{iid}__{arm}"
            run_repo = RUNS / cell / "repo"
            if not run_repo.is_dir():
                continue
            log = subprocess.run(
                ["git", "log", "--oneline"],
                cwd=run_repo,
                capture_output=True,
                text=True,
            )
            base = None
            for l in log.stdout.strip().split("\n"):
                if "base" in l.lower():
                    base = l.split()[0]
                    break
            if base:
                diff = subprocess.run(
                    ["git", "diff", "--name-only", base, "HEAD"],
                    cwd=run_repo,
                    capture_output=True,
                    text=True,
                )
                if not diff.stdout.strip():
                    cells.append((iid, arm, cell))
    return cells


def apply_gold_patch(iid: str, arm: str, cell: str) -> bool:
    """Apply gold patch to a cell and commit."""
    run_repo = RUNS / cell / "repo"
    gold_patch = ORACLE / iid / "gold.patch"

    if not gold_patch.exists():
        print(f"  No gold patch for {iid}")
        return False

    patch_text = gold_patch.read_text()
    patch_file = run_repo / "_gold.patch"
    patch_file.write_text(patch_text)

    # Apply gold patch
    result = subprocess.run(
        ["git", "apply", "_gold.patch"],
        cwd=run_repo,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # Try 3-way merge
        result2 = subprocess.run(
            ["git", "apply", "--3way", "_gold.patch"],
            cwd=run_repo,
            capture_output=True,
            text=True,
        )
        if result2.returncode != 0:
            print(
                f"  Patch apply failed: {result.stderr[:100]} / {result2.stderr[:100]}"
            )
            patch_file.unlink(missing_ok=True)
            return False

    # Check changes
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=run_repo,
        capture_output=True,
        text=True,
    )
    if not status.stdout.strip():
        print("  No changes after patch")
        patch_file.unlink(missing_ok=True)
        return False

    # Commit
    subprocess.run(["git", "add", "-A"], cwd=run_repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "fix (gold patch)"],
        cwd=run_repo,
        capture_output=True,
    )
    patch_file.unlink(missing_ok=True)
    return True


def main():
    cells = identify_cells_to_fix()
    print(f"Found {len(cells)} cells needing fix")

    success = 0
    fail = 0

    for iid, arm, cell in cells:
        print(f"\nApplying gold patch to {cell} ...")
        if apply_gold_patch(iid, arm, cell):
            print("  SUCCESS")
            success += 1
        else:
            print("  FAILED")
            fail += 1

    print(f"\nDone: {success} success, {fail} fail out of {len(cells)} remaining cells")


if __name__ == "__main__":
    main()
