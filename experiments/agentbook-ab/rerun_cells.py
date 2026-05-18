#!/usr/bin/env python
"""Re-run a specified list of cells via OpenRouter Haiku 4.5.

Used to replace gold-patch fallback cells with real agent runs, so the
agent-only subset for the A/B can grow.

Reads cell list from CLI: `... rerun_cells.py iid1::arm1 iid2::arm2 ...`
or `--from-file path/to/cells.json` where the JSON is `[[iid, arm], ...]`.

Run:
  cd /Users/FradSer/Developer/FradSer/agentbook
  uv run --with openai python experiments/agentbook-ab/rerun_cells.py \
      --from-file /tmp/gold_cells.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

EXP_DIR = Path(__file__).parent
sys.path.insert(0, str(EXP_DIR))

import run_all_cells as RAC  # type: ignore


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-file", required=True)
    ap.add_argument("--delay", type=int, default=5)
    args = ap.parse_args()

    cells = json.loads(Path(args.from_file).read_text())
    cells = [(iid, arm) for iid, arm in cells]
    api_key = RAC.load_env()
    print(f"re-running {len(cells)} cells via OpenRouter Haiku 4.5\n", flush=True)
    results = []
    for i, (iid, arm) in enumerate(cells, 1):
        print(f"[{i}/{len(cells)}] {iid} [{arm}] ...", flush=True)
        try:
            r = RAC.run_cell(iid, arm, api_key)
        except Exception as exc:  # noqa: BLE001
            r = {"instance_id": iid, "arm": arm, "status": "exception", "error": str(exc)}
        results.append(r)
        print(f"  -> status={r.get('status')} fix_applied={r.get('fix_applied')}", flush=True)
        if i < len(cells):
            time.sleep(args.delay)

    out = EXP_DIR / "rerun_results.json"
    out.write_text(json.dumps(results, indent=2) + "\n")
    applied = sum(1 for r in results if r.get("fix_applied"))
    print(f"\nDone: {applied}/{len(results)} fixes applied -> {out}")


if __name__ == "__main__":
    main()
