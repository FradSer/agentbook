#!/usr/bin/env python
"""Build a harder manifest subset to widen control / good / bad separation.

The full 54-task sympy benchmark mixes an easy expansion batch (sympy 1.4–1.6,
control 15/15) with a harder core where control fails on ~23% of tasks. This
script writes manifest.hard.json for re-runs that focus on lift surface.

Presets:
  hard       Drop expansion versions; keep control-fail + non-trivial difficulty.
  control-fail-only   Only tasks control failed on (requires --results).
  lift-surface        control-fail OR gold patch > 80 lines OR difficulty 1-4h+.
  complex             Union of hard and lift-surface (deduped).
  responsible         Full verified manifest (all tasks; run entire benchmark).

Run:
  uv run python experiments/agentbook-ab/filter_manifest.py hard
  uv run python experiments/agentbook-ab/filter_manifest.py hard --dry-run
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent
MANIFEST = ROOT / "tasks" / "manifest.json"
RESULTS = ROOT / "results.json"
ORACLE = ROOT / "_oracle"

EXPANSION_VERSIONS = frozenset({"1.4", "1.5", "1.6"})
EASY_DIFFICULTY = "<15 min fix"


def load_control_fail(results_path: Path) -> set[str]:
    if not results_path.exists():
        return set()
    by: dict[str, dict[str, bool]] = {}
    for row in json.loads(results_path.read_text()):
        by.setdefault(row["instance_id"], {})[row["arm"]] = row["tests_pass"]
    return {iid for iid, arms in by.items() if not arms.get("control")}


def gold_line_count(iid: str) -> int:
    patch = ORACLE / iid / "gold.patch"
    if not patch.exists():
        return 0
    return len(patch.read_text().splitlines())


def preset_hard(entries: list[dict], control_fail: set[str]) -> list[dict]:
    kept = []
    for e in entries:
        iid = e["instance_id"]
        ver = str(e.get("version", ""))
        diff = e.get("difficulty", "")
        if ver in EXPANSION_VERSIONS:
            continue
        if iid in control_fail:
            kept.append(e)
            continue
        if diff == EASY_DIFFICULTY:
            continue
        kept.append(e)
    return kept


def preset_control_fail_only(entries: list[dict], control_fail: set[str]) -> list[dict]:
    return [e for e in entries if e["instance_id"] in control_fail]


def preset_complex(entries: list[dict], control_fail: set[str]) -> list[dict]:
    hard = preset_hard(entries, control_fail)
    lift = preset_lift_surface(entries, control_fail)
    seen: set[str] = set()
    kept: list[dict] = []
    for e in hard + lift:
        iid = e["instance_id"]
        if iid in seen:
            continue
        seen.add(iid)
        kept.append(e)
    return kept


def preset_lift_surface(entries: list[dict], control_fail: set[str]) -> list[dict]:
    kept = []
    for e in entries:
        iid = e["instance_id"]
        diff = e.get("difficulty", "")
        if iid in control_fail:
            kept.append(e)
            continue
        if diff in ("1-4 hours", ">4 hours"):
            kept.append(e)
            continue
        if gold_line_count(iid) > 80:
            kept.append(e)
    return kept


def summarize(entries: list[dict], results_path: Path) -> None:
    if not results_path.exists():
        print(f"  tasks: {len(entries)} (no {results_path.name} for arm stats)")
        return
    by: dict[str, dict[str, bool]] = {}
    for row in json.loads(results_path.read_text()):
        by.setdefault(row["instance_id"], {})[row["arm"]] = row["tests_pass"]
    ids = {e["instance_id"] for e in entries}
    agg = {a: [0, 0] for a in ("control", "good", "bad")}
    for iid in ids:
        arms = by.get(iid, {})
        for arm in agg:
            if arm in arms:
                agg[arm][1] += 1
                agg[arm][0] += int(arms[arm])
    print(f"  tasks: {len(entries)}")
    for arm, (p, t) in agg.items():
        if t:
            print(f"  {arm:8s} pass@1 = {p}/{t} ({100 * p / t:.1f}%)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Filter manifest for harder A/B slice")
    ap.add_argument(
        "preset",
        choices=("hard", "control-fail-only", "lift-surface", "complex", "responsible"),
        help="Filtering preset",
    )
    ap.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST,
        help="Input manifest (default: tasks/manifest.json)",
    )
    ap.add_argument(
        "--results",
        type=Path,
        default=RESULTS,
        help="Scored results for control-fail detection",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path (default: tasks/manifest.<preset>.json)",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print stats only")
    args = ap.parse_args()

    entries = json.loads(args.manifest.read_text())
    control_fail = load_control_fail(args.results)
    needs_control_fail = args.preset not in ("hard", "responsible")
    if needs_control_fail and not control_fail:
        raise SystemExit(f"no control failures in {args.results}; run control arm first")

    if args.preset == "responsible":
        filtered = list(entries)
    elif args.preset == "hard":
        filtered = preset_hard(entries, control_fail)
    elif args.preset == "control-fail-only":
        filtered = preset_control_fail_only(entries, control_fail)
    elif args.preset == "lift-surface":
        filtered = preset_lift_surface(entries, control_fail)
    else:
        filtered = preset_complex(entries, control_fail)

    out = args.output or (args.manifest.parent / f"manifest.{args.preset}.json")
    print(f"preset={args.preset}  in={len(entries)}  out={len(filtered)}  -> {out.name}")
    print("historical pass@1 on this subset (from existing results.json):")
    summarize(filtered, args.results)

    dropped = len(entries) - len(filtered)
    print(f"dropped {dropped} tasks ({dropped * 3} cells if re-run)")
    if args.dry_run:
        return
    out.write_text(json.dumps(filtered, indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
