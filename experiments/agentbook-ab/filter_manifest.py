#!/usr/bin/env python
"""Generate manifest presets from verified tasks and control-fail / lift data.

Presets:
  hard          Drop sympy 1.4-1.6 expansion; drop <15 min unless control-failed.
  lift          Hard tier + control did not PASS (primary A/B lift surface).
  multirepo     Sympy hard tier + verified sklearn/pytest pilot tasks.
  lift-multirepo  Lift-eligible sympy hard + sklearn pilot.

Run:
  uv run python filter_manifest.py lift -o tasks/manifest.lift.json
  uv run python filter_manifest.py lift-multirepo -o tasks/manifest.lift.multirepo.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent
TASKS = ROOT / "tasks"
DEFAULT_MANIFEST = TASKS / "manifest.json"
RESULTS_OPENROUTER = ROOT / "results.openrouter.json"
RESULTS_STRONG = ROOT / "results.sympy.json"

EXPANSION_VERSIONS = frozenset({"1.4", "1.5", "1.6"})
CONTROL_FAIL_FALLBACK = frozenset(
    {
        "sympy__sympy-14976",
        "sympy__sympy-15349",
        "sympy__sympy-15599",
        "sympy__sympy-16597",
        "sympy__sympy-17630",
        "sympy__sympy-18199",
        "sympy__sympy-19040",
        "sympy__sympy-19346",
        "sympy__sympy-19495",
        "sympy__sympy-19783",
        "sympy__sympy-20154",
        "sympy__sympy-20428",
        "sympy__sympy-20438",
        "sympy__sympy-20590",
        "sympy__sympy-20801",
        "sympy__sympy-21379",
        "sympy__sympy-21596",
        "sympy__sympy-21612",
        "sympy__sympy-21930",
        "sympy__sympy-22080",
        "sympy__sympy-22456",
        "sympy__sympy-22914",
        "sympy__sympy-23262",
        "sympy__sympy-23413",
        "sympy__sympy-23824",
        "sympy__sympy-23950",
        "sympy__sympy-24066",
        "sympy__sympy-24213",
        "sympy__sympy-24443",
        "sympy__sympy-24661",
    }
)

PILOT_REPOS = frozenset({"scikit-learn/scikit-learn", "pytest-dev/pytest"})


def load_entries(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def control_fail_ids() -> set[str]:
    """Tasks where control submitted and failed (legacy hard-tier helper)."""
    for path in (RESULTS_STRONG, RESULTS_OPENROUTER):
        if not path.is_file():
            continue
        rows = json.loads(path.read_text())
        failed = {
            r["instance_id"]
            for r in rows
            if r.get("arm") == "control"
            and r.get("submitted")
            and not r.get("tests_pass")
        }
        if failed:
            return failed
    return set(CONTROL_FAIL_FALLBACK)


def lift_eligible_ids(manifest_ids: set[str]) -> set[str]:
    from benchmark.eligibility import resolve_lift_eligible_ids

    return resolve_lift_eligible_ids(
        manifest_ids,
        strong_results=RESULTS_STRONG,
        weak_results=RESULTS_OPENROUTER,
        fallback=CONTROL_FAIL_FALLBACK,
    )


def preset_hard(entries: list[dict], control_fail: set[str]) -> list[dict]:
    out: list[dict] = []
    for e in entries:
        repo = e.get("repo", "")
        if repo != "sympy/sympy":
            continue
        version = str(e.get("version", ""))
        if version in EXPANSION_VERSIONS:
            continue
        diff = e.get("difficulty", "")
        if diff == "<15 min fix" and e["instance_id"] not in control_fail:
            continue
        out.append(e)
    return out


def preset_lift(entries: list[dict], control_fail: set[str]) -> list[dict]:
    hard = preset_hard(entries, control_fail)
    eligible = lift_eligible_ids({e["instance_id"] for e in hard})
    return [e for e in hard if e["instance_id"] in eligible]


def verified_pilot_tasks() -> list[dict]:
    out: list[dict] = []
    for meta_path in sorted(TASKS.glob("*/META.json")):
        iid = meta_path.parent.name
        if iid.startswith("_"):
            continue
        meta = json.loads(meta_path.read_text())
        if not meta.get("verified"):
            continue
        repo = meta.get("repo", "")
        if repo not in PILOT_REPOS:
            continue
        out.append(
            {
                "instance_id": iid,
                "repo": repo,
                "version": str(meta.get("version", "")),
                "difficulty": meta.get("difficulty", ""),
            }
        )
    return sorted(out, key=lambda e: e["instance_id"])


def preset_multirepo(entries: list[dict], control_fail: set[str]) -> list[dict]:
    hard = preset_hard(entries, control_fail)
    pilot = verified_pilot_tasks()
    seen = {e["instance_id"] for e in hard}
    merged = list(hard)
    for e in pilot:
        if e["instance_id"] not in seen:
            merged.append(e)
            seen.add(e["instance_id"])
    return merged


def preset_lift_multirepo(entries: list[dict], control_fail: set[str]) -> list[dict]:
    lift = preset_lift(entries, control_fail)
    pilot = verified_pilot_tasks()
    seen = {e["instance_id"] for e in lift}
    merged = list(lift)
    for e in pilot:
        if e["instance_id"] not in seen:
            merged.append(e)
            seen.add(e["instance_id"])
    return merged


PRESETS = {
    "hard": preset_hard,
    "lift": preset_lift,
    "multirepo": preset_multirepo,
    "lift-multirepo": preset_lift_multirepo,
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Filter manifest presets")
    ap.add_argument(
        "preset",
        choices=sorted(PRESETS),
        help="Preset name",
    )
    ap.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Source manifest (default: tasks/manifest.json)",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Output manifest path",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts only; do not write output",
    )
    args = ap.parse_args()

    entries = load_entries(args.manifest)
    control_fail = control_fail_ids()
    filtered = PRESETS[args.preset](entries, control_fail)

    print(f"preset={args.preset}  source={len(entries)}  output={len(filtered)}")
    if args.preset in ("lift", "lift-multirepo"):
        eligible = lift_eligible_ids({e["instance_id"] for e in entries})
        print(f"  lift-eligible pool: {len(eligible)} (from strong/weak control scores)")
    by_repo: dict[str, int] = {}
    for e in filtered:
        by_repo[e.get("repo", "?")] = by_repo.get(e.get("repo", "?"), 0) + 1
    for repo, n in sorted(by_repo.items()):
        print(f"  {repo}: {n}")

    if args.dry_run:
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(filtered, indent=2) + "\n")
    print(f"wrote -> {args.output}")


if __name__ == "__main__":
    main()
