#!/usr/bin/env python
"""Final report: does agentbook lift small models toward Opus 4.7?

Scans every result archive (runs_v2.* + live runs_v2/), pairs each small model's
control/good/oracle on the 17 Opus-solved memory tasks, computes resolved-rate
(SKIP=FAIL), exact-binomial McNemar and paired bootstrap CI, and frames each
against the Opus 4.7 ceiling (claude -p) and published SWE-bench numbers.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent
ORACLE = ROOT / "_oracle"
import sys

sys.path.insert(0, str(ROOT))
from stats.bootstrap import bootstrap_delta  # noqa: E402
from stats.metrics import (  # noqa: E402
    arm_rate,
    build_outcomes,
    paired_units,
)
from stats.paired import mcnemar  # noqa: E402

# archive dir -> display label
ARCHIVES = {
    "runs_v2.local-gptoss": "gpt-oss:20b (local Ollama)",
    "runs_v2.local-e4b": "gemma4:e4b (local Ollama)",
    "runs_v2.openrouter-gptoss-free": "gpt-oss-20b:free (OpenRouter)",
    "runs_v2": "(live run)",
}


def load_archive(d: Path):
    rows = [json.loads(f.read_text()) for f in d.glob("*/result.json")]
    return rows


def model_block(rows: list[dict], label: str) -> dict:
    recs = [
        {
            "model": label,
            "arm": r["arm"],
            "instance_id": r["instance_id"],
            "resolved": r["resolved"],
        }
        for r in rows
    ]
    out = build_outcomes(recs)
    block = {"label": label, "n_cells": len(rows)}
    for arm in ("control", "good", "oracle"):
        key = (label, arm)
        if key in out:
            for crit in ("any", "strict"):
                _, res, tot = arm_rate(out[key], crit)
                block[f"{arm}_{crit}"] = f"{res}/{tot}"
    pu = paired_units(out, label, "control", "good", "any")
    if pu:
        block["mcnemar"] = mcnemar(pu)
        block["bootstrap"] = bootstrap_delta(pu, b=10000, seed=1)
    block["submit_rate"] = (
        round(sum(1 for r in rows if r["submitted"]) / len(rows), 3) if rows else 0
    )
    block["good_lift_tasks"] = sorted(
        {
            r["instance_id"].split("-")[-1]
            for r in rows
            if r["arm"] == "good" and r["resolved"]
        }
        - {
            r["instance_id"].split("-")[-1]
            for r in rows
            if r["arm"] == "control" and r["resolved"]
        }
    )
    return block


def main() -> None:
    opus = json.loads((ORACLE / "solver_verified.json").read_text())
    red = {
        e["instance_id"]
        for e in json.loads((ROOT / "tasks/manifest.red.json").read_text())
    }
    opus_red = [r for r in opus if r["instance_id"] in red]
    opus_solved = sum(1 for r in opus_red if r.get("resolved"))
    layer1 = json.loads((ROOT / "retrieval_report.json").read_text())
    pub = json.loads((ORACLE / "published_benchmarks.json").read_text())

    blocks = []
    for d, label in ARCHIVES.items():
        p = ROOT / d
        if not p.is_dir():
            continue
        rows = load_archive(p)
        if rows:
            blocks.append(model_block(rows, label))

    report = {
        "opus_ceiling": {
            "model": "Claude Opus 4.7 (claude -p, no hint)",
            "red_set": f"{opus_solved}/{len(opus_red)} = {opus_solved / len(opus_red):.0%}",
            "memory_set": "17/17 (the good-arm tasks are exactly Opus-solved tasks)",
        },
        "layer1_retrieval": {k: layer1[k] for k in layer1 if k != "per_task"},
        "small_models": blocks,
        "published_reference": pub["published"],
        "reproduction_gap": pub["reproduction_gap"],
    }
    (ROOT / "final_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
