"""Red-phase test for the confound-isolating `control_loop` arm in
`pipeline.arm_context`.

The measured good_loop lift over control mixes three effects that are
inseparable without a new arm: the harness apply-failure fix, the generic
apply->verify->retry loop scaffold, and the injected memory itself. `control_loop`
carries the SAME verification repros good_loop carries (so the loop, done-gate,
and rollback in `harness.agent_loop.run_episode` fire identically) but injects
NO memory block -- the prompt is the bare `control` bug prompt. The control vs
control_loop delta therefore measures the loop+apply-fix scaffold alone,
isolating it from the memory.

Fixture strategy mirrors test_arm_context.py: the real
`sympy__sympy-15017` task BUG.md is read by both arms (no TASKS monkeypatch
needed), and `SYNTH_CACHE` is pointed at a fixture cache so the verification
repros are deterministic. `_synth_data` (the module memo) is reset to force a
re-read.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline import arm_context as arm_ctx  # noqa: E402

_IID = "sympy__sympy-15017"

_MEMORY_MARKER = "## agentbook memory"


def _write_synth_cache(cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                _IID: {
                    "root_cause_pattern": (
                        "rank-0 array length guard returns 0 instead of 1"
                    ),
                    "localization_cues": [
                        "pkg/mod0.py: `__len__` early-exit branch",
                    ],
                    "verifications": [
                        "python -c 'import pkg; assert len(pkg.zero()) == 1'",
                        "python -c 'import pkg; assert list(pkg.zero())'",
                    ],
                    "verification_method": "python -c 'import pkg; pkg.check()'",
                }
            }
        )
    )


def test_control_loop_carries_verification_without_memory(tmp_path, monkeypatch):
    """Scenario: control_loop = control prompt + good_loop verification repros.

    Given a synth cache entry for `sympy__sympy-15017` with two verification
    repros, when build_prompt(iid, "control_loop") runs, then:
      - the prompt is byte-identical to the `control` prompt (no recall / synth /
        memory block injected);
      - arm_meta carries the SAME verification repros good_loop would carry, so
        the harness apply->verify->retry loop fires identically;
      - arm_meta records the arm hint and carries no `synth`/`apply_patch` keys.
    """
    cache_path = tmp_path / "_oracle" / "synth_cache.json"
    _write_synth_cache(cache_path)

    monkeypatch.setattr(arm_ctx, "SYNTH_CACHE", cache_path)
    monkeypatch.setattr(arm_ctx, "_synth_data", None)

    control_prompt, _ = arm_ctx.build_prompt(_IID, "control")
    prompt, meta = arm_ctx.build_prompt(_IID, "control_loop")

    # No memory of any kind is injected: the prompt equals the bare control
    # prompt, so the control vs control_loop delta isolates the loop scaffold.
    assert prompt == control_prompt
    assert _MEMORY_MARKER not in prompt
    assert "agentbook memory" not in prompt
    assert "root cause" not in prompt.lower()

    # The verification repros good_loop carries are present, so the harness
    # loop, done-gate, and rollback fire identically to good_loop.
    _, loop_meta = arm_ctx.build_prompt(_IID, "good_loop")
    assert meta["verification"] == loop_meta["verification"]
    assert meta["verification"]["repros"] == [
        "python -c 'import pkg; assert len(pkg.zero()) == 1'",
        "python -c 'import pkg; assert list(pkg.zero())'",
    ]

    # No memory metadata leaks into the arm context.
    assert meta["hint"] == "control_loop"
    assert "synth" not in meta
    assert "apply_patch" not in meta


def test_control_loop_cache_miss_drops_verification(tmp_path, monkeypatch):
    """Without a verification cache entry, control_loop degenerates to control:
    no verification repros, so the gate (`loop_ids`) keeps it out of the sweep
    rather than dispatching a cell that would equal plain control."""
    cache_path = tmp_path / "_oracle" / "synth_cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({}))

    monkeypatch.setattr(arm_ctx, "SYNTH_CACHE", cache_path)
    monkeypatch.setattr(arm_ctx, "_synth_data", None)

    control_prompt, _ = arm_ctx.build_prompt(_IID, "control")
    prompt, meta = arm_ctx.build_prompt(_IID, "control_loop")

    assert prompt == control_prompt
    assert meta.get("cache_miss") is True
    assert "verification" not in meta
