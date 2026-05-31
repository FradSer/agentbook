"""Red-phase test for orchestrator per-(iid, model) chain scheduling.

Maps 1:1 to bdd-specs.md Feature 4 scenario 8 (R6): the orchestrator dispatches
good_rotate cells as per-(iid, model) chains where samples within one chain run
serially (so sample N+1's _load_prior_sample_outcomes finds sample N's
result.json on disk), while chains across distinct (iid, model) pairs may
overlap in wall time (chain-level parallelism preserved).

Fixture strategy:
  - Stub `pipeline.orchestrator.run_cell` with a thread-safe recorder; it
    captures (iid, model, sample_idx, start_ts, end_ts), sleeps for a small
    bounded delay (~50 ms) so wall-clock overlap is detectable, and writes a
    synthetic result.json into runs_v2/<dirname>/ so any downstream
    _load_prior_sample_outcomes call would find it.
  - The test redirects RUNS_V2 to a tmp_path so we don't touch the real
    runs_v2/ directory.
  - The test invokes `pipeline.orchestrator.run_chain` (does not yet exist ->
    AttributeError = the expected Red shape per task-012 step 4).
"""

from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from harness import sandbox as sandbox_mod  # noqa: E402

from pipeline import orchestrator as orch_mod  # noqa: E402
from pipeline.grid import Cell  # noqa: E402

_SLEEP_SECS = 0.05


def _make_recorder(records, lock):
    """Build a thread-safe stub for run_cell.

    The stub captures wall-clock interval per call and writes a synthetic
    result.json with arm_meta.routed_to so _load_prior_sample_outcomes (if ever
    consulted by a real build_prompt downstream) would find it.
    """

    def _stub(cell, llm, client, **_kwargs):
        start_ts = time.monotonic()
        time.sleep(_SLEEP_SECS)
        end_ts = time.monotonic()
        with lock:
            records.append(
                {
                    "iid": cell.iid,
                    "model": cell.model,
                    "sample_idx": cell.sample_idx,
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                }
            )
        cell.run_dir.mkdir(parents=True, exist_ok=True)
        synthetic = {
            "instance_id": cell.iid,
            "arm": cell.arm,
            "model": cell.model,
            "model_slug": cell.model_slug,
            "sample_idx": cell.sample_idx,
            "resolved": False,
            "arm_meta": {
                "hint": "good_rotate",
                "routed_from": "good_rotate",
                "routed_to": "good_multi_loop",
                "rotate_sample_idx": cell.sample_idx,
            },
        }
        (cell.run_dir / "result.json").write_text(json.dumps(synthetic) + "\n")
        return synthetic

    return _stub


def test_good_rotate_chain_runs_serial_within_chain(tmp_path, monkeypatch):
    """BDD Feature 4 / scenario 8 (R6):

      Given the orchestrator enumerates 3 good_rotate cells for
            (sympy__sympy-15017, gemma4:e4b) at sample_idx=0/1/2
      And   the run_chain function dispatches them as a single chain
      When  the chain executes under args.workers=12
      Then  sample_idx=1 starts only after sample_idx=0's result.json has been
            written to runs_v2/
      And   sample_idx=2 starts only after sample_idx=1's result.json has been
            written
      And   other tasks' chains may execute in parallel (chain-level
            parallelism preserved)
      And   no two cells in the SAME chain ever overlap in wall time

    Red shape: `pipeline.orchestrator.run_chain` does not yet exist ->
    AttributeError on the symbol fetch.
    """
    # Redirect runs_v2/ to tmp_path so the stub's writes never touch the real
    # archive (CODE-TEST-01).
    monkeypatch.setattr(sandbox_mod, "RUNS_V2", tmp_path)

    records: list[dict] = []
    lock = threading.Lock()
    monkeypatch.setattr(orch_mod, "run_cell", _make_recorder(records, lock))

    # Two distinct (iid, model) chains; three sample indices each.
    chains_input = []
    for iid, model in (
        ("sympy__sympy-15017", "google/gemma-3-4b-it"),
        ("sympy__sympy-15976", "google/gemma-3-4b-it"),
    ):
        chains_input.append(
            [
                Cell(iid=iid, arm="good_rotate", model=model, sample_idx=s)
                for s in range(3)
            ]
        )

    # Expected Red: run_chain does not exist yet.
    run_chain = orch_mod.run_chain  # type: ignore[attr-defined]

    # Dispatch chains in parallel; cells within a chain must run serially.
    workers = 12
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [
            ex.submit(
                run_chain,
                chain,
                None,  # llm
                None,  # client
                step_budget=1,
                temperature=0.0,
                seed_base=0,
                bash_timeout=1,
            )
            for chain in chains_input
        ]
        for fut in futs:
            fut.result()

    # All 6 cells executed.
    assert len(records) == 6, records

    # Group records by chain.
    by_chain: dict[tuple[str, str], list[dict]] = {}
    for rec in records:
        by_chain.setdefault((rec["iid"], rec["model"]), []).append(rec)

    # (a) Start timestamps monotonically increase by sample_idx within each chain.
    # (b) No two cells in the same chain overlap in wall time.
    for key, rows in by_chain.items():
        rows.sort(key=lambda r: r["sample_idx"])
        for i in range(1, len(rows)):
            prev, cur = rows[i - 1], rows[i]
            assert cur["start_ts"] > prev["start_ts"], (
                f"chain {key} sample {cur['sample_idx']} did not start after "
                f"sample {prev['sample_idx']}"
            )
            assert cur["start_ts"] >= prev["end_ts"], (
                f"chain {key} cell {cur['sample_idx']} started "
                f"({cur['start_ts']:.4f}) before cell {prev['sample_idx']} "
                f"ended ({prev['end_ts']:.4f}) -- in-chain overlap"
            )

    # (c) Across chains, at least one pair of cells from different chains
    # overlap in wall time (chain-level parallelism is preserved).
    chain_keys = list(by_chain.keys())
    assert len(chain_keys) >= 2
    rows_a = by_chain[chain_keys[0]]
    rows_b = by_chain[chain_keys[1]]
    overlapping = 0
    for ra in rows_a:
        for rb in rows_b:
            if ra["start_ts"] < rb["end_ts"] and rb["start_ts"] < ra["end_ts"]:
                overlapping += 1
    assert overlapping >= 1, (
        "expected at least one cross-chain overlap to confirm chain-level "
        f"parallelism; got 0 (rows_a={rows_a}, rows_b={rows_b})"
    )


# --------------------------------------------------------------------------- #
# BATCH4-013-B rework: _has_memory good_rotate branch                         #
# --------------------------------------------------------------------------- #


def test_has_memory_good_rotate_branch():
    """BATCH4-013-B: `_has_memory` must require ALL three sub-arm prerequisites
    (mem_ids, synth_ids, loop_ids) for the `good_rotate` arm.

    Red shape: pre-fix `_has_memory` has no `good_rotate` branch (falls through
    to `return True`), so a good_rotate cell whose iid lacks any sub-arm cache
    would silently dispatch and crash at the recursive sub-arm call. The test
    fails because the function is not yet exposed at module-level and/or always
    returns True for good_rotate.
    """
    iid_full = "sympy__sympy-15017"
    iid_no_synth = "sympy__sympy-15976"
    iid_no_loop = "sympy__sympy-16450"
    iid_no_mem = "sympy__sympy-13647"

    mem_ids = {iid_full, iid_no_synth, iid_no_loop}
    synth_ids = {iid_full, iid_no_loop, iid_no_mem}
    loop_ids = {iid_full, iid_no_synth, iid_no_mem}

    def _cell(iid: str):
        return Cell(
            iid=iid,
            arm="good_rotate",
            model="google/gemma-3-4b-it",
            sample_idx=0,
        )

    # Reference the symbol up-front so the Red shape is a clean AttributeError
    # when `_has_memory` is not yet exposed module-level.
    has_memory = orch_mod._has_memory  # type: ignore[attr-defined]

    # All three prerequisites satisfied -> True.
    assert has_memory(_cell(iid_full), mem_ids, synth_ids, loop_ids) is True, (
        "good_rotate with all three caches should be allowed"
    )

    # Missing synth_ids -> False.
    assert has_memory(_cell(iid_no_synth), mem_ids, synth_ids, loop_ids) is False, (
        "good_rotate without synth cache should be gated out"
    )

    # Missing loop_ids -> False.
    assert has_memory(_cell(iid_no_loop), mem_ids, synth_ids, loop_ids) is False, (
        "good_rotate without loop cache should be gated out"
    )

    # Missing mem_ids -> False.
    assert has_memory(_cell(iid_no_mem), mem_ids, synth_ids, loop_ids) is False, (
        "good_rotate without recall cache should be gated out"
    )


# --------------------------------------------------------------------------- #
# BATCH4-013-A rework: main() scheduling splits rotate vs non-rotate          #
# --------------------------------------------------------------------------- #


def test_orchestrator_main_splits_rotate_cells_into_chains(tmp_path, monkeypatch):
    """BATCH4-013-A: the orchestrator's dispatch step must split the `todo`
    list into rotate-chains (serial within (iid, model)) and a parallel pool
    for everything else.

    Fixture:
      - 2 good_rotate cells for (iid_A, model_X) at sample_idx 0 and 1.
      - 1 good cell for (iid_B, model_X) (must go through the parallel pool).

    Expected behaviour:
      - the two rotate cells' wall-clock intervals never overlap (chain
        serialisation);
      - the `good` cell's interval may overlap with EITHER rotate cell (the
        parallel pool runs alongside the chain pool).

    Red shape: pre-fix `main()` dispatches every cell through a single
    ThreadPoolExecutor with workers >= 3; the two rotate cells run in parallel
    and their wall-clock intervals overlap. The structural failure is on the
    `_dispatch_todo` attribute fetch when the helper does not yet exist.
    """
    monkeypatch.setattr(sandbox_mod, "RUNS_V2", tmp_path)

    records: list[dict] = []
    lock = threading.Lock()
    monkeypatch.setattr(orch_mod, "run_cell", _make_recorder(records, lock))

    model_x = "google/gemma-3-4b-it"
    iid_a = "sympy__sympy-15017"
    iid_b = "sympy__sympy-15976"

    todo = [
        Cell(iid=iid_a, arm="good_rotate", model=model_x, sample_idx=0),
        Cell(iid=iid_a, arm="good_rotate", model=model_x, sample_idx=1),
        Cell(iid=iid_b, arm="good", model=model_x, sample_idx=0),
    ]

    # Expected Red: _dispatch_todo does not exist yet -> AttributeError.
    dispatch = orch_mod._dispatch_todo  # type: ignore[attr-defined]

    dispatch(
        todo,
        llm=None,
        client=None,
        workers=12,
        step_budget=1,
        temperature=0.0,
        seed_base=0,
        bash_timeout=1,
    )

    assert len(records) == 3, records

    rotate_rows = sorted(
        [r for r in records if r["iid"] == iid_a],
        key=lambda r: r["sample_idx"],
    )
    other_rows = [r for r in records if r["iid"] == iid_b]
    assert len(rotate_rows) == 2
    assert len(other_rows) == 1

    # Within the rotate chain: strict serial ordering (sample 0 ends before
    # sample 1 starts). This fails pre-fix because both rotate cells would
    # be dispatched through the single parallel pool and run concurrently.
    assert rotate_rows[1]["start_ts"] >= rotate_rows[0]["end_ts"], (
        f"rotate chain not serialised: sample 1 started "
        f"({rotate_rows[1]['start_ts']:.4f}) before sample 0 ended "
        f"({rotate_rows[0]['end_ts']:.4f}) -- main() did not route "
        f"good_rotate through run_chain"
    )

    # Chain-level parallelism preserved: the good cell's interval must overlap
    # with at least one rotate cell's interval (proves it ran on Pool A
    # concurrently with the chain pool).
    good = other_rows[0]
    overlaps = any(
        good["start_ts"] < r["end_ts"] and r["start_ts"] < good["end_ts"]
        for r in rotate_rows
    )
    assert overlaps, (
        "expected the non-rotate good cell to overlap with at least one "
        f"rotate cell in wall time (parallel pool); got good={good} "
        f"rotate_rows={rotate_rows}"
    )


# --------------------------------------------------------------------------- #
# control_loop confound-isolation arm: _has_memory gates on loop_ids           #
# --------------------------------------------------------------------------- #


def test_has_memory_control_loop_gates_on_loop_ids():
    """`control_loop` reuses good_loop's verification cache (no memory block),
    so `_has_memory` must gate it on `loop_ids` exactly like good_loop -- not on
    mem_ids/synth_ids. A control_loop cell whose iid lacks a runnable repro
    check would equal plain control, so it must be skipped.
    """
    iid_loop = "sympy__sympy-15017"
    iid_no_loop = "sympy__sympy-16450"

    mem_ids = {iid_loop, iid_no_loop}
    synth_ids = {iid_loop, iid_no_loop}
    loop_ids = {iid_loop}

    def _cell(iid: str):
        return Cell(
            iid=iid,
            arm="control_loop",
            model="google/gemma-3-4b-it",
            sample_idx=0,
        )

    has_memory = orch_mod._has_memory

    assert has_memory(_cell(iid_loop), mem_ids, synth_ids, loop_ids) is True, (
        "control_loop with a verification cache should be allowed"
    )
    assert has_memory(_cell(iid_no_loop), mem_ids, synth_ids, loop_ids) is False, (
        "control_loop without a verification cache should be gated out"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
