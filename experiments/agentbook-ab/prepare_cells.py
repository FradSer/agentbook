#!/usr/bin/env python
"""Prepare run workspaces and cell list for an A/B batch.

Reads prompts.json, resets each runs/<id>__<arm>/repo from the pristine task
copy, and writes prompt.md + prompt_used.md for sub-agents or OpenRouter.

Run:
  uv run python experiments/agentbook-ab/prepare_cells.py \\
      --prompts prompts.complex.json \\
      -o /tmp/complex_cells.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXP = Path(__file__).parent
sys.path.insert(0, str(EXP))

from cell_workspace import prepare_run_dir  # noqa: E402

ROOT = EXP
RUNS = ROOT / "runs"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--prompts",
        type=Path,
        default=ROOT / "prompts.json",
        help="Prompts JSON from build_prompts.py",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=ROOT / "cells_to_run.json",
        help="Output [[instance_id, arm], ...] for agent batch runners",
    )
    ap.add_argument(
        "--runs-dir",
        type=Path,
        default=RUNS,
        help="Run directory root (default: runs/)",
    )
    args = ap.parse_args()

    prompts = json.loads(args.prompts.read_text())
    cells: list[list[str]] = []
    for key, spec in sorted(prompts.items()):
        iid = spec["instance_id"]
        arm = spec["arm"]
        run_dir = args.runs_dir / f"{iid}__{arm}"
        run_dir.mkdir(parents=True, exist_ok=True)
        prepare_run_dir(iid, arm, runs_dir=args.runs_dir)
        prompt = spec["prompt"]
        (run_dir / "prompt.md").write_text(prompt)
        (run_dir / "prompt_used.md").write_text(prompt)
        cells.append([iid, arm])

    args.output.write_text(json.dumps(cells, indent=2) + "\n")
    print(f"prepared {len(cells)} cells under {args.runs_dir} -> {args.output}")


if __name__ == "__main__":
    main()
