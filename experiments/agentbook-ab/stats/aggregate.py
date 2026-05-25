#!/usr/bin/env python
"""Scan runs_v2/*/result.json into a single aggregate with a source_fingerprint.

The fingerprint binds the aggregate to the exact run artifacts it summarizes, so
a stale aggregate (runs re-executed after aggregation) is detectable.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.sandbox import RUNS_V2  # noqa: E402
from pipeline.freshness import fingerprint  # noqa: E402

AGG_OUT = RUNS_V2 / "_aggregate.json"

_FIELDS = (
    "instance_id",
    "arm",
    "model",
    "model_slug",
    "sample_idx",
    "submitted",
    "tests_pass",
    "resolved",
    "stop_reason",
    "turns_used",
    "diff_lines",
    "seed",
    "temperature",
)


def collect(runs_v2: Path = RUNS_V2) -> list[dict]:
    records: list[dict] = []
    for result in sorted(runs_v2.glob("*/result.json")):
        try:
            r = json.loads(result.read_text())
        except json.JSONDecodeError:
            continue
        rec = {k: r.get(k) for k in _FIELDS}
        am = r.get("arm_meta") or {}
        rec["no_good_match"] = am.get("no_good_match")
        rec["top_similarity"] = am.get("top_similarity")
        records.append(rec)
    return records


def main() -> None:
    records = collect()
    agg = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_fingerprint": fingerprint(),
        "n_samples": len(records),
        "records": records,
    }
    AGG_OUT.write_text(json.dumps(agg, indent=2) + "\n")
    models = sorted({r["model"] for r in records if r.get("model")})
    arms = sorted({r["arm"] for r in records if r.get("arm")})
    print(f"aggregated {len(records)} samples | models={models} arms={arms}")
    print(f"-> {AGG_OUT} (fingerprint {agg['source_fingerprint']})")


if __name__ == "__main__":
    main()
