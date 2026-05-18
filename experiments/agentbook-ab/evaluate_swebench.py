#!/usr/bin/env python
"""Run official SWE-bench harness evaluation on exported predictions (Docker).

This is the reproducible, public grading path for the full SWE-bench Verified
substrate (500 instances, all repos). Requires Docker and the `swebench` package.

Prerequisites:
  1. fetch_verified.py  — download dataset from Hugging Face
  2. export_predictions.py — produce JSONL from runs/
  3. Docker daemon running

Example:
  uv run python experiments/agentbook-ab/export_predictions.py \\
    --arm good -o experiments/agentbook-ab/predictions/good.jsonl

  uv run --with swebench python experiments/agentbook-ab/evaluate_swebench.py \\
    --predictions experiments/agentbook-ab/predictions/good.jsonl \\
    --run_id agentbook-good-001

Official docs: https://www.swebench.com/SWE-bench/guides/evaluation/
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "_data" / "verified.parquet"


def main() -> None:
    ap = argparse.ArgumentParser(description="SWE-bench Verified Docker evaluation")
    ap.add_argument("--predictions", type=Path, required=True)
    ap.add_argument("--run_id", required=True, help="Unique id for this eval run")
    ap.add_argument(
        "--max_workers",
        type=int,
        default=4,
        help="Parallel Docker workers (lower if RAM-limited)",
    )
    ap.add_argument(
        "--instance_ids",
        nargs="*",
        help="Optional subset of instance ids to evaluate",
    )
    args = ap.parse_args()

    if not DATA.exists():
        raise SystemExit(f"Missing {DATA}; run fetch_verified.py first")
    if not args.predictions.is_file():
        raise SystemExit(f"Predictions file not found: {args.predictions}")

    cmd = [
        sys.executable,
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        "SWE-bench/SWE-bench_Verified",
        "--predictions_path",
        str(args.predictions.resolve()),
        "--run_id",
        args.run_id,
        "--max_workers",
        str(args.max_workers),
    ]
    if args.instance_ids:
        cmd.extend(["--instance_ids", *args.instance_ids])

    print("Running:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
