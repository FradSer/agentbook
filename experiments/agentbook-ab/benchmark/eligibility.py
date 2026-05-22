"""Lift-eligible task selection — tasks where control did not pass.

The A/B lift surface is tasks the unaided agent fails or skips. Measuring
good vs control on tasks control already passes compresses rag_gain toward zero.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.paths import EXP_ROOT

DEFAULT_STRONG_RESULTS = EXP_ROOT / "results.sympy.json"
DEFAULT_WEAK_RESULTS = EXP_ROOT / "results.openrouter.sympy.json"


def load_scored_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        return data.get("results", [])
    return data


def control_unpassed_ids(
    rows: list[dict],
    manifest_ids: set[str],
) -> set[str]:
    """Instance IDs where control arm did not achieve PASS."""
    control: dict[str, dict] = {}
    for row in rows:
        if row.get("arm") != "control":
            continue
        control[row["instance_id"]] = row

    eligible: set[str] = set()
    for iid in manifest_ids:
        row = control.get(iid)
        if row is None:
            eligible.add(iid)
            continue
        if not row.get("submitted"):
            eligible.add(iid)
        elif not row.get("tests_pass"):
            eligible.add(iid)
    return eligible


def resolve_lift_eligible_ids(
    manifest_ids: set[str],
    *,
    strong_results: Path = DEFAULT_STRONG_RESULTS,
    weak_results: Path = DEFAULT_WEAK_RESULTS,
    fallback: set[str] | frozenset[str] | None = None,
) -> set[str]:
    """Prefer strong-model control scores; fall back to weak or static list."""
    for path in (strong_results, weak_results):
        rows = load_scored_rows(path)
        if rows:
            found = control_unpassed_ids(rows, manifest_ids)
            if found:
                return found
    if fallback:
        return {iid for iid in fallback if iid in manifest_ids}
    return manifest_ids
