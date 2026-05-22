"""Unit tests for lift-eligible task selection."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3] / "experiments" / "agentbook-ab"
ELIGIBILITY = ROOT / "benchmark" / "eligibility.py"
FILTER = ROOT / "filter_manifest.py"


def _load_module(path: Path, name: str):
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_control_unpassed_ids() -> None:
    mod = _load_module(ELIGIBILITY, "eligibility")
    rows = [
        {"instance_id": "a", "arm": "control", "submitted": True, "tests_pass": True},
        {"instance_id": "b", "arm": "control", "submitted": True, "tests_pass": False},
        {"instance_id": "c", "arm": "control", "submitted": False},
    ]
    eligible = mod.control_unpassed_ids(rows, {"a", "b", "c", "d"})
    assert eligible == {"b", "c", "d"}


def test_lift_preset_excludes_control_pass_tasks(tmp_path: Path) -> None:
    mod = _load_module(FILTER, "filter_manifest")
    results = tmp_path / "results.sympy.json"
    results.write_text(
        json.dumps(
            [
                {
                    "instance_id": "sympy__sympy-15345",
                    "arm": "control",
                    "submitted": True,
                    "tests_pass": True,
                },
                {
                    "instance_id": "sympy__sympy-14976",
                    "arm": "control",
                    "submitted": True,
                    "tests_pass": False,
                },
            ]
        )
    )
    mod.RESULTS_STRONG = results
    entries = json.loads((ROOT / "tasks" / "manifest.json").read_text())
    control_fail = mod.control_fail_ids()
    lift = mod.preset_lift(entries, control_fail)
    ids = {e["instance_id"] for e in lift}
    assert "sympy__sympy-15345" not in ids
    assert "sympy__sympy-14976" in ids
