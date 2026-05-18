"""Manifest filtering — static presets (no circular dependency on results.json)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from benchmark.paths import DEFAULT_MANIFEST, EXP_ROOT, ORACLE

EXPANSION_VERSIONS = frozenset({"1.4", "1.5", "1.6"})
EASY_DIFFICULTY = "<15 min fix"
MIN_GOLD_LINES_V2 = 15


def gold_line_count(iid: str) -> int:
    patch = ORACLE / iid / "gold.patch"
    if not patch.exists():
        return 0
    return len(patch.read_text().splitlines())


def load_entries(manifest_path: Path) -> list[dict]:
    return json.loads(manifest_path.read_text())


def preset_full(entries: list[dict], _cf: set[str]) -> list[dict]:
    return list(entries)


def preset_eval_v2(entries: list[dict], _cf: set[str]) -> list[dict]:
    """Static hard eval slice: non-expansion, non-trivial difficulty, min gold size."""
    kept = []
    for e in entries:
        ver = str(e.get("version", ""))
        diff = e.get("difficulty", "")
        iid = e["instance_id"]
        if ver in EXPANSION_VERSIONS:
            continue
        if diff == EASY_DIFFICULTY:
            continue
        if gold_line_count(iid) < MIN_GOLD_LINES_V2:
            continue
        kept.append(e)
    return kept


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


def preset_complex(entries: list[dict], control_fail: set[str]) -> list[dict]:
    seen: set[str] = set()
    kept: list[dict] = []
    for e in preset_hard(entries, control_fail) + preset_lift_surface(entries, control_fail):
        iid = e["instance_id"]
        if iid in seen:
            continue
        seen.add(iid)
        kept.append(e)
    return kept


PRESETS: dict[str, Callable[[list[dict], set[str]], list[dict]]] = {
    "full": preset_full,
    "responsible": preset_full,
    "eval-v2": preset_eval_v2,
    "hard": preset_hard,
    "lift-surface": preset_lift_surface,
    "complex": preset_complex,
}


def load_control_fail(results_path: Path) -> set[str]:
    if not results_path.exists():
        return set()
    by: dict[str, dict[str, bool]] = {}
    for row in json.loads(results_path.read_text()):
        by.setdefault(row["instance_id"], {})[row["arm"]] = row["tests_pass"]
    return {iid for iid, arms in by.items() if not arms.get("control")}


def filter_manifest(
    preset: str,
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    results_path: Path | None = None,
    require_control_fail: bool = False,
) -> list[dict]:
    if preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}; choose from {sorted(PRESETS)}")
    entries = load_entries(manifest_path)
    control_fail = load_control_fail(results_path or EXP_ROOT / "results.json")
    fn = PRESETS[preset]
    needs_cf = require_control_fail or preset in ("hard", "lift-surface", "complex")
    if needs_cf and preset not in ("eval-v2", "full", "responsible") and not control_fail:
        raise SystemExit(f"no control failures in {results_path}; run control arm first")
    return fn(entries, control_fail)


def write_manifest(preset: str, out: Path | None = None, **kwargs) -> Path:
    filtered = filter_manifest(preset, **kwargs)
    path = out or (DEFAULT_MANIFEST.parent / f"manifest.{preset}.json")
    path.write_text(json.dumps(filtered, indent=2) + "\n")
    return path
