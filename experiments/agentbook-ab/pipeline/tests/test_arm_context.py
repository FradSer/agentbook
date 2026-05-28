"""Red-phase test for the `good_rotate` arm branch in `pipeline.arm_context`.

The single test maps 1:1 to scenario 7 of Feature 4 in
docs/plans/2026-05-27-agentbook-outcome-loop-design/bdd-specs.md:

    "good_rotate cell records the routing decision in arm_meta"

Fixture strategy:
  - `tmp_path` materialises a fake `runs_v2/<iid>__good_rotate__<model>__s0/
    result.json` carrying `arm_meta.routed_to="good_multi_loop"` and
    `resolved=False`, plus a minimal `_oracle/synth_cache.json` containing
    one entry for `sympy__sympy-15017` so `extract_features` succeeds.
  - Module-level path constants (`SYNTH_CACHE` on both `pipeline.arm_context`
    and `pipeline.router`, and a runs root the new `_load_prior_sample_outcomes`
    consults) are monkeypatched to the fixture tree.
  - `_synth_data` (the module-level memo) is reset to avoid leakage from
    sibling tests.
  - The shared `pipeline.router._ACTIVE_ROUTER` global stays at its
    default `RuleRouter()`; the test asserts only that the chosen sub-arm is
    in `RUNTIME_ARMS` and is not the rotation arm itself, so it is robust
    against future router default swaps within the runtime arm pool.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline import arm_context as arm_ctx  # noqa: E402
from pipeline import router as router_mod  # noqa: E402
from pipeline.router import RUNTIME_ARMS  # noqa: E402

_IID = "sympy__sympy-15017"
_MODEL = "gemma4_e4b"


def _write_prior_sample(runs_root: Path) -> None:
    cell_dir = runs_root / f"{_IID}__good_rotate__{_MODEL}__s0"
    cell_dir.mkdir(parents=True, exist_ok=True)
    (cell_dir / "result.json").write_text(
        json.dumps(
            {
                "resolved": False,
                "arm_meta": {"routed_to": "good_multi_loop"},
            }
        )
    )


def _write_synth_cache(cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                _IID: {
                    "root_cause_pattern": (
                        "branch guard inverted: condition test reversed at "
                        "the loop boundary"
                    ),
                    "localization_cues": [
                        "pkg/mod0.py: `_compute` early-exit branch",
                        "pkg/mod1.py: `_finalize` mirrors the same guard",
                        "third hint mentioning branch and pkg/mod0.py",
                        "fourth hint about pkg/mod1.py",
                        "fifth pointer back to pkg/mod0.py",
                    ],
                    "verifications": [
                        "repro_0.py",
                        "repro_1.py",
                        "repro_2.py",
                        "repro_3.py",
                        "repro_4.py",
                    ],
                    "verification_method": "python -c 'import pkg; pkg.check()'",
                }
            }
        )
    )


def test_good_rotate_cell_records_arm_meta(tmp_path, monkeypatch):
    """Scenario: good_rotate cell records the routing decision in arm_meta.

    Given the prior sample at sample_idx=0 has arm_meta.routed_to="good_multi_loop"
    and resolved=False, when build_prompt(iid, "good_rotate", ..., sample_idx=1)
    runs, then the returned arm_meta must carry routed_from="good_rotate",
    routed_to=<chosen sub-arm in RUNTIME_ARMS and != "good_rotate">,
    rotate_sample_idx=1, and rotate_tried_history={"good_multi_loop": [False]}.
    """
    runs_root = tmp_path / "runs_v2"
    runs_root.mkdir()
    _write_prior_sample(runs_root)

    cache_path = tmp_path / "_oracle" / "synth_cache.json"
    _write_synth_cache(cache_path)

    # Point both modules at the fixture cache and runs root.
    monkeypatch.setattr(arm_ctx, "SYNTH_CACHE", cache_path)
    monkeypatch.setattr(router_mod, "SYNTH_CACHE", cache_path)
    monkeypatch.setattr(arm_ctx, "RUNS_V2", runs_root, raising=False)
    # Force `_synth_entry`'s memo to re-read the fixture cache.
    monkeypatch.setattr(arm_ctx, "_synth_data", None)

    _, meta = arm_ctx.build_prompt(
        _IID,
        "good_rotate",
        client=None,
        model_slug=_MODEL,
        sample_idx=1,
    )

    assert meta["routed_from"] == "good_rotate"
    assert meta["routed_to"] in RUNTIME_ARMS
    assert meta["routed_to"] != "good_rotate"
    assert meta["rotate_sample_idx"] == 1
    assert meta["rotate_tried_history"] == {"good_multi_loop": [False]}
