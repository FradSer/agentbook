#!/usr/bin/env python
"""Summarize three-arm A/B results (control / good / oracle).

Computes pass@1, paired lift/harm, retrieval_loss, rag_gain.

Run:
  uv run python summarize_ab.py results.sympy.json --manifest tasks/manifest.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent


def load_results(path: Path) -> dict[tuple[str, str], dict]:
    rows = json.loads(path.read_text())
    out: dict[tuple[str, str], dict] = {}
    for row in rows:
        out[(row["instance_id"], row["arm"])] = row
    return out


def pass_status(row: dict | None) -> str | None:
    if row is None:
        return None
    if not row.get("submitted"):
        return "SKIP"
    return "PASS" if row.get("tests_pass") else "FAIL"


def main() -> None:
    ap = argparse.ArgumentParser(description="Summarize control/good/oracle A/B")
    ap.add_argument("results", type=Path, help="JSON from score.py")
    ap.add_argument("--manifest", type=Path, default=ROOT / "tasks" / "manifest.json")
    ap.add_argument("-o", "--output", type=Path, help="Optional JSON summary")
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text())
    results = load_results(args.results)
    arms = ("control", "good", "oracle")
    manifest_ids = {e["instance_id"] for e in manifest}

    def is_lift_eligible(iid: str) -> bool:
        row = results.get((iid, "control"))
        if row is None:
            return True
        if not row.get("submitted"):
            return True
        return not row.get("tests_pass")

    eligible_ids = {iid for iid in manifest_ids if is_lift_eligible(iid)}

    print(f"\n{'instance':<36} {'control':>10} {'good':>10} {'oracle':>10}")
    print("-" * 70)

    paired_cg: list[tuple[str, str, str]] = []
    paired_go: list[tuple[str, str, str]] = []

    for entry in manifest:
        iid = entry["instance_id"]
        statuses = {a: pass_status(results.get((iid, a))) for a in arms}
        def fmt(s: str | None) -> str:
            if s is None:
                return "   —"
            if s == "SKIP":
                return "  SKIP"
            return s.rjust(10)

        print(f"{iid:<36} {fmt(statuses['control'])} {fmt(statuses['good'])} {fmt(statuses['oracle'])}")

        if statuses["control"] in ("PASS", "FAIL") and statuses["good"] in ("PASS", "FAIL"):
            paired_cg.append((iid, statuses["control"], statuses["good"]))
        if statuses["good"] in ("PASS", "FAIL") and statuses["oracle"] in ("PASS", "FAIL"):
            paired_go.append((iid, statuses["good"], statuses["oracle"]))

    paired_cg_eligible = [
        t for t in paired_cg if t[0] in eligible_ids and t[1] == "FAIL"
    ]

    agg: dict[str, dict[str, int]] = defaultdict(lambda: {"pass": 0, "submitted": 0, "skip": 0})
    agg_eligible: dict[str, dict[str, int]] = defaultdict(
        lambda: {"pass": 0, "submitted": 0, "skip": 0}
    )
    for arm in arms:
        for entry in manifest:
            iid = entry["instance_id"]
            row = results.get((iid, arm))
            buckets = [agg]
            if iid in eligible_ids:
                buckets.append(agg_eligible)
            for bucket in buckets:
                if row is None or not row.get("submitted"):
                    bucket[arm]["skip"] += 1
                    continue
                bucket[arm]["submitted"] += 1
                if row.get("tests_pass"):
                    bucket[arm]["pass"] += 1

    print("-" * 70)
    for arm in arms:
        a = agg[arm]
        rate = f"{100 * a['pass'] / a['submitted']:.1f}%" if a["submitted"] else "n/a"
        print(
            f"  {arm:8s} pass@1 = {a['pass']}/{a['submitted']} ({rate})"
            f"  |  skipped: {a['skip']}"
        )

    def paired_stats(pairs: list[tuple[str, str, str]], left: str, right: str) -> dict:
        lift = harm = both_pass = both_fail = 0
        lifted: list[str] = []
        harmed: list[str] = []
        for iid, l, r in pairs:
            if l == "FAIL" and r == "PASS":
                lift += 1
                lifted.append(iid)
            elif l == "PASS" and r == "FAIL":
                harm += 1
                harmed.append(iid)
            elif l == "PASS" and r == "PASS":
                both_pass += 1
            elif l == "FAIL" and r == "FAIL":
                both_fail += 1
        return {
            "n": len(pairs),
            "lift": lift,
            "harm": harm,
            "both_pass": both_pass,
            "both_fail": both_fail,
            "lifted": lifted,
            "harmed": harmed,
        }

    cg = paired_stats(paired_cg, "control", "good")
    cg_eligible = paired_stats(paired_cg_eligible, "control", "good")
    go = paired_stats(paired_go, "good", "oracle")

    ctrl_pass = agg["control"]["pass"]
    good_pass = agg["good"]["pass"]
    oracle_pass = agg["oracle"]["pass"]
    ctrl_pass_e = agg_eligible["control"]["pass"]
    good_pass_e = agg_eligible["good"]["pass"]
    oracle_pass_e = agg_eligible["oracle"]["pass"]

    print(f"\nLift-eligible tasks (control != PASS): {len(eligible_ids)}/{len(manifest_ids)}")
    for arm in arms:
        a = agg_eligible[arm]
        rate = f"{100 * a['pass'] / a['submitted']:.1f}%" if a["submitted"] else "n/a"
        print(
            f"  {arm:8s} pass@1 = {a['pass']}/{a['submitted']} ({rate})"
            f"  |  skipped: {a['skip']}"
        )

    print(f"\nPaired control vs good (n={cg['n']}):")
    print(f"  lift={cg['lift']} harm={cg['harm']} both_pass={cg['both_pass']} both_fail={cg['both_fail']}")
    print(f"  rag_gain (good-control pass): {good_pass - ctrl_pass:+d}")

    print(
        f"\nPaired on lift-eligible where control FAIL (n={cg_eligible['n']}):"
    )
    print(
        f"  lift={cg_eligible['lift']} harm=0 "
        f"both_fail={cg_eligible['both_fail']}"
    )
    print(
        f"  rag_gain_eligible (good-control pass on eligible): "
        f"{good_pass_e - ctrl_pass_e:+d}"
    )

    print(f"\nPaired good vs oracle (n={go['n']}):")
    print(f"  lift={go['lift']} harm={go['harm']} both_pass={go['both_pass']} both_fail={go['both_fail']}")
    print(f"  retrieval_loss (oracle-good pass): {oracle_pass - good_pass:+d}")

    summary = {
        "results_file": str(args.results),
        "manifest": str(args.manifest),
        "lift_eligible_tasks": len(eligible_ids),
        "pass_at_1": {a: agg[a] for a in arms},
        "pass_at_1_eligible": {a: agg_eligible[a] for a in arms},
        "submit_rate": {
            a: round(agg[a]["submitted"] / len(manifest_ids), 4) if manifest_ids else 0.0
            for a in arms
        },
        "paired_control_good": cg,
        "paired_control_good_eligible_fail": cg_eligible,
        "paired_good_oracle": go,
        "rag_gain": good_pass - ctrl_pass,
        "rag_gain_eligible": good_pass_e - ctrl_pass_e,
        "retrieval_loss": oracle_pass - good_pass,
        "retrieval_loss_eligible": oracle_pass_e - good_pass_e,
    }
    if args.output:
        args.output.write_text(json.dumps(summary, indent=2) + "\n")
        print(f"\nsummary -> {args.output}")


if __name__ == "__main__":
    main()
