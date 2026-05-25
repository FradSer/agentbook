#!/usr/bin/env python
"""Assemble the final report from runs_v2/_aggregate.json.

Produces report.json (machine) + REPORT.md (human). Headlines the panel-pooled
good - control resolved-rate lift with a 95% bootstrap CI and an exact-binomial
McNemar p-value, for both pass@k (any-of-k) and strict (all-of-k) criteria; and
the good - oracle ceiling gap. Embeds the source_fingerprint and a freshness
check so the report cannot silently drift from the run artifacts.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.sandbox import RUNS_V2  # noqa: E402
from pipeline.freshness import check, fingerprint  # noqa: E402

from stats.bootstrap import bootstrap_delta  # noqa: E402
from stats.metrics import (  # noqa: E402
    arm_rate,
    build_outcomes,
    diagnostics,
    paired_units,
    pooled_units,
)
from stats.paired import mcnemar  # noqa: E402

AGG = RUNS_V2 / "_aggregate.json"
PANEL = RUNS_V2 / "_panel.json"
BUDGET = RUNS_V2 / "_budget.json"
RETRIEVAL = ROOT / "retrieval_report.json"
REPORT_JSON = ROOT / "report.json"
REPORT_MD = ROOT / "REPORT.md"

CRITERIA = {"pass@k": "any", "strict": "strict"}


def _inference(outcomes, models, arm_a, arm_b, crit):
    out = {"per_model": {}, "pooled": {}}
    for m in models:
        pairs = paired_units(outcomes, m, arm_a, arm_b, crit)
        out["per_model"][m] = {**mcnemar(pairs), **bootstrap_delta(pairs)}
    pooled = pooled_units(outcomes, models, arm_a, arm_b, crit)
    out["pooled"] = {**mcnemar(pooled), **bootstrap_delta(pooled)}
    return out


def build_report() -> dict:
    if not AGG.exists():
        sys.exit("missing runs_v2/_aggregate.json; run stats.aggregate first")
    agg = json.loads(AGG.read_text())
    records = agg["records"]
    outcomes = build_outcomes(records)
    models = sorted({r["model"] for r in records if r.get("model")})
    arms = [
        a
        for a in ("control", "good", "oracle")
        if any((m, a) in outcomes for m in models)
    ]

    rates: dict = {}
    for label, crit in CRITERIA.items():
        rates[label] = {"per_model": {}, "pooled": {}}
        for m in models:
            rates[label]["per_model"][m] = {}
            for a in arms:
                r, res, tot = arm_rate(outcomes.get((m, a), {}), crit)
                rates[label]["per_model"][m][a] = {
                    "rate": round(r, 4),
                    "resolved": res,
                    "tasks": tot,
                }
        for a in arms:
            per = [rates[label]["per_model"][m][a]["rate"] for m in models]
            rates[label]["pooled"][a] = round(sum(per) / len(per), 4) if per else 0.0

    inference: dict = {}
    for label, crit in CRITERIA.items():
        inference[label] = {
            "good_vs_control": _inference(outcomes, models, "control", "good", crit),
        }
        if "oracle" in arms:
            inference[label]["oracle_vs_good"] = _inference(
                outcomes, models, "good", "oracle", crit
            )

    diag = {f"{m}|{a}": v for (m, a), v in diagnostics(records).items()}

    provenance = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_fingerprint": agg.get("source_fingerprint"),
        "aggregate_fresh": check(AGG),
        "live_fingerprint": fingerprint(),
        "n_samples": agg.get("n_samples"),
        "models": models,
        "arms": arms,
        "panel": json.loads(PANEL.read_text()) if PANEL.exists() else None,
        "budget": json.loads(BUDGET.read_text()) if BUDGET.exists() else None,
        "harness_git_commit": (
            records[0].get("harness_git_commit") if records else None
        ),
    }
    layer1 = json.loads(RETRIEVAL.read_text()) if RETRIEVAL.exists() else None

    return {
        "provenance": provenance,
        "layer1_retrieval": (
            {k: layer1[k] for k in layer1 if k != "per_task"} if layer1 else None
        ),
        "rates": rates,
        "inference": inference,
        "diagnostics": diag,
    }


def _fmt_md(rep: dict) -> str:
    p = rep["provenance"]
    L = []
    L.append("# Does agentbook help WEAK coding models? (rebuilt eval)\n")
    L.append(
        f"_Generated {p['generated_at']} · fingerprint `{p['source_fingerprint']}` "
        f"· fresh: {p['aggregate_fresh']} · {p['n_samples']} samples_\n"
    )
    L.append("## Provenance\n")
    L.append(f"- Models (panel): {', '.join(p['models']) or '(none)'}")
    L.append(f"- Arms: {', '.join(p['arms'])}")
    if p.get("budget"):
        L.append(f"- OpenRouter day budget: {p['budget']}")
    L.append(f"- Harness commit: `{p['harness_git_commit']}`\n")

    if rep.get("layer1_retrieval"):
        r = rep["layer1_retrieval"]
        L.append("## Layer 1 -- honest retrieval (no ab_task tag; sympy distractors)\n")
        L.append(f"- tasks={r.get('tasks')} distractors={r.get('distractors_seeded')}")
        L.append(
            f"- recall@1={r.get('recall@1')} recall@3={r.get('recall@3')} "
            f"recall@5={r.get('recall@5')} MRR={r.get('mrr')}"
        )
        L.append(
            f"- wins_above_distractors={r.get('wins_above_distractors')} "
            f"(embed={r.get('embedding_provider')}, rerank={r.get('rerank_provider')})\n"
        )

    for label in CRITERIA:
        L.append(f"## Layer 2 -- resolved-rate ({label}, SKIP=FAIL)\n")
        header = "| model | " + " | ".join(rep["provenance"]["arms"]) + " |"
        L.append(header)
        L.append("|" + "---|" * (len(rep["provenance"]["arms"]) + 1))
        for m in p["models"]:
            cells = []
            for a in p["arms"]:
                d = rep["rates"][label]["per_model"][m][a]
                cells.append(f"{d['rate']:.2f} ({d['resolved']}/{d['tasks']})")
            L.append(f"| {m} | " + " | ".join(cells) + " |")
        pooled = rep["rates"][label]["pooled"]
        L.append(
            "| **pooled** | "
            + " | ".join(f"**{pooled[a]:.2f}**" for a in p["arms"])
            + " |\n"
        )

        inf = rep["inference"][label]["good_vs_control"]["pooled"]
        L.append(
            f"**good - control (pooled, {label}):** "
            f"Δ={inf['delta']:+.3f} 95% CI [{inf['ci_low']:+.3f}, {inf['ci_high']:+.3f}] "
            f"· lift={inf['lift']} harm={inf['harm']} n={inf['n']} "
            f"· McNemar p={inf['p_value']:.4f}\n"
        )
        if "oracle_vs_good" in rep["inference"][label]:
            o = rep["inference"][label]["oracle_vs_good"]["pooled"]
            L.append(
                f"**oracle - good (pooled, {label}, retrieval ceiling gap):** "
                f"Δ={o['delta']:+.3f} 95% CI [{o['ci_low']:+.3f}, {o['ci_high']:+.3f}] "
                f"· n={o['n']}\n"
            )

    L.append("## Diagnostics (submit/skip/turns per model-arm)\n")
    L.append("| model\\|arm | samples | submit | skip | mean turns |")
    L.append("|---|---|---|---|---|")
    for key, d in sorted(rep["diagnostics"].items()):
        L.append(
            f"| {key} | {d['samples']} | {d['submit_rate']} | "
            f"{d['skip_rate']} | {d['mean_turns']} |"
        )
    L.append("\n## Caveats\n")
    L.append(
        "- Free-model nondeterminism: seeds recorded but providers may ignore them."
    )
    L.append(
        "- Single repo (sympy), no Docker; cross-repo generalization is future work."
    )
    L.append(
        "- good memories exist only for tasks the strong solver verifiably solved."
    )
    return "\n".join(L) + "\n"


def main() -> None:
    rep = build_report()
    REPORT_JSON.write_text(json.dumps(rep, indent=2) + "\n")
    REPORT_MD.write_text(_fmt_md(rep))
    p = rep["provenance"]
    print(f"report -> {REPORT_JSON} and {REPORT_MD}")
    print(
        f"fresh={p['aggregate_fresh']} models={len(p['models'])} samples={p['n_samples']}"
    )
    for label in CRITERIA:
        inf = rep["inference"][label]["good_vs_control"]["pooled"]
        print(
            f"  {label}: good-control pooled Δ={inf['delta']:+.3f} "
            f"CI[{inf['ci_low']:+.3f},{inf['ci_high']:+.3f}] p={inf['p_value']:.4f}"
        )


if __name__ == "__main__":
    main()
