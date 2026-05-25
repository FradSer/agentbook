#!/usr/bin/env python
"""Score the strong-solver workspaces with the tamper-proof score.py core.

Only tasks the strong solver GENUINELY solved (FAIL_TO_PASS passes after the
held-out test_patch) qualify to become `good` memories -- guaranteeing each
seeded memory describes a real, correct peer-agent fix.

Usage:
  uv run python -m memory.verify_solution
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from benchmark.paths import DEFAULT_MANIFEST, ORACLE, TASKS  # noqa: E402
from score import score_run_dir  # noqa: E402

from memory.strong_solver import SOLVER_ROOT  # noqa: E402

VERIFIED_OUT = ORACLE / "solver_verified.json"


def verify_all(manifest_path: Path) -> list[dict]:
    manifest = json.loads(manifest_path.read_text())
    out: list[dict] = []
    for entry in manifest:
        iid = entry["instance_id"]
        run_dir = SOLVER_ROOT / f"{iid}__solver"
        meta = json.loads((TASKS / iid / "META.json").read_text())
        if not (run_dir / "repo").is_dir():
            out.append({"instance_id": iid, "ran": False, "resolved": False})
            continue
        print(f"scoring strong solver: {iid} ...", flush=True)
        res = score_run_dir(meta, run_dir, arm="solver")
        resolved = bool(res.get("submitted") and res.get("tests_pass"))
        out.append(
            {
                "instance_id": iid,
                "ran": True,
                "submitted": res.get("submitted"),
                "tests_pass": res.get("tests_pass"),
                "resolved": resolved,
                "diff_lines": res.get("diff_lines"),
                "summary": res.get("summary"),
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify strong-solver attempts")
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = ap.parse_args()

    results = verify_all(args.manifest)
    VERIFIED_OUT.write_text(json.dumps(results, indent=2) + "\n")
    n_resolved = sum(1 for r in results if r.get("resolved"))
    n_ran = sum(1 for r in results if r.get("ran"))
    print(
        f"\nstrong solver resolved {n_resolved}/{n_ran} ran "
        f"({len(results)} tasks total) -> {VERIFIED_OUT}"
    )


if __name__ == "__main__":
    main()
