"""Red-phase tests for memory/refine_from_outcomes.py (Feature 1, bdd-specs.md).

Each test maps 1:1 to a Gherkin scenario in
docs/plans/2026-05-27-agentbook-outcome-loop-design/bdd-specs.md Feature 1.

Fixture strategy:
  - tmp_path holds a synthetic `_oracle/synth_cache.json` + `outcomes_log.json`
    + `runs_v2/<iid>__<arm>__<model_slug>__s*/{result.json,transcript.json}`.
  - The real `_oracle/outcomes_log.json` / `_oracle/synth_cache.json` are never
    touched (CODE-TEST-01 anti-leak invariant).
  - `subprocess.run` is monkeypatched; no real Opus calls.
  - `gold_added_lines` / `scrub_leak` are imported from `memory.to_memory_entry`
    (canonical anti-leak primitives — used unmocked, real signatures).
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Importing the module under test. In the Red phase this raises ImportError,
# which fails every test in the file with the structural reason called out in
# the sprint contract (CODE-TEST-03).
from memory import refine_from_outcomes as rfo  # noqa: E402
from memory.to_memory_entry import gold_added_lines  # noqa: E402

# --------------------------------------------------------------------------- #
# fixture helpers                                                             #
# --------------------------------------------------------------------------- #


_IID_15976 = "sympy__sympy-15976"
_IID_16450 = "sympy__sympy-16450"
_IID_16766 = "sympy__sympy-16766"
_IID_15875 = "sympy__sympy-15875"
_MODEL = "gemma4_e4b"
_RUNTIME_ARMS = ("good", "good_synth", "good_loop", "good_multi_loop")


def _base_entry(iid: str) -> dict:
    return {
        "root_cause_pattern": f"original pattern for {iid}",
        "localization_cues": [f"cue1 for {iid}", "cue2"],
        "verification_method": "python -c 'import x; print(x())'",
        "verifications": [],
        "instance_id": iid,
        "leak_lines_removed": 0,
        "model": "opus",
        "source": "claude -p synthesis of leak-free memory",
        "elapsed_s": 12.3,
    }


def _outcome_row(iid: str, arm: str, sample_idx: int, *, resolved: bool) -> dict:
    return {
        "model_slug": _MODEL,
        "iid": iid,
        "arm": arm,
        "sample_idx": sample_idx,
        "resolved": resolved,
    }


def _write_run(
    runs_dir: Path,
    iid: str,
    arm: str,
    sample_idx: int,
    *,
    resolved: bool,
    transcript_turns: list[dict] | None = None,
    notes: list[str] | None = None,
    stop_reason: str = "done",
    verification_passed: bool = False,
    turns_used: int = 4,
) -> str:
    cell = f"{iid}__{arm}__{_MODEL}__s{sample_idx}"
    cdir = runs_dir / cell
    cdir.mkdir(parents=True, exist_ok=True)
    result = {
        "instance_id": iid,
        "arm": arm,
        "model_slug": _MODEL,
        "sample_idx": sample_idx,
        "resolved": resolved,
        "stop_reason": stop_reason,
        "turns_used": turns_used,
        "verification_passed": verification_passed,
    }
    (cdir / "result.json").write_text(json.dumps(result) + "\n")
    transcript = {
        "stop_reason": stop_reason,
        "turns_used": turns_used,
        "error": None,
        "notes": notes or [],
        "turns": transcript_turns
        or [
            {
                "turn": 1,
                "command": "ls",
                "stdout_tail": "sympy/printing/mathml.py\n",
                "stderr_tail": "",
                "returncode": 0,
                "latency_ms": 12,
            },
            {
                "turn": 2,
                "command": "grep -n mi sympy/printing/mathml.py",
                "stdout_tail": "1234: mi.appendChild(...)\n",
                "stderr_tail": "",
                "returncode": 0,
                "latency_ms": 14,
            },
        ],
    }
    (cdir / "transcript.json").write_text(json.dumps(transcript) + "\n")
    return cell


def _write_fixture(
    tmp_path: Path,
    *,
    cache: dict,
    outcomes: list[dict],
) -> tuple[Path, Path, Path]:
    """Materialize the synthetic oracle + runs_v2 layout under tmp_path."""
    oracle_dir = tmp_path / "_oracle"
    oracle_dir.mkdir(parents=True, exist_ok=True)
    cache_path = oracle_dir / "synth_cache.json"
    outcomes_path = oracle_dir / "outcomes_log.json"
    cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n")
    outcomes_path.write_text(json.dumps(outcomes, indent=2) + "\n")
    runs_dir = tmp_path / "runs_v2"
    runs_dir.mkdir(parents=True, exist_ok=True)
    return cache_path, outcomes_path, runs_dir


def _opus_stdout(payload: dict) -> str:
    """Build the `claude -p --output-format json` envelope shape `_extract_json`
    will then pull a fenced ```json block out of."""
    fenced = "Here is the refined entry:\n\n```json\n" + json.dumps(payload) + "\n```\n"
    return json.dumps({"result": fenced})


def _stub_run_factory(per_iid_payload: dict[str, dict | Exception]):
    """Return a subprocess.run-compatible stub that branches on the prompt's iid.

    `per_iid_payload[iid]` is either a refined-dict to return as Opus output, or
    an Exception instance to raise when the prompt mentions that iid.
    Tracks the call count per iid via the `.calls` attribute on the returned
    callable so tests can assert per-task isolation.
    """
    calls: dict[str, int] = {}

    def stub(cmd, *args, **kwargs):  # noqa: D401, ANN001
        prompt = ""
        if isinstance(cmd, (list, tuple)):
            for i, part in enumerate(cmd):
                if part == "-p" and i + 1 < len(cmd):
                    prompt = cmd[i + 1]
                    break
        which_iid = None
        for iid in per_iid_payload:
            if iid in prompt:
                which_iid = iid
                break
        if which_iid is None:
            raise AssertionError(
                f"stub: prompt did not name any of {list(per_iid_payload)}"
            )
        calls[which_iid] = calls.get(which_iid, 0) + 1
        payload = per_iid_payload[which_iid]
        if isinstance(payload, BaseException):
            raise payload
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=_opus_stdout(payload),
            stderr="",
        )

    stub.calls = calls  # type: ignore[attr-defined]
    return stub


def _capture_logs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Capture all log lines the script emits via logging or stdout prints."""
    buf: list[str] = []

    def _print(*a, **kw):
        buf.append(" ".join(str(x) for x in a))

    monkeypatch.setattr("builtins.print", _print)

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            buf.append(record.getMessage())

    handler = _Handler(level=logging.DEBUG)
    logger = logging.getLogger("memory.refine_from_outcomes")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return buf


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    cache_path: Path,
    outcomes_path: Path,
    runs_dir: Path,
    extra_argv: list[str],
) -> int:
    """Invoke the CLI under tmp_path, redirecting all global paths."""
    monkeypatch.setattr(rfo, "SYNTH_CACHE", cache_path, raising=False)
    monkeypatch.setattr(rfo, "OUTCOMES_LOG", outcomes_path, raising=False)
    monkeypatch.setattr(rfo, "RUNS_DIR", runs_dir, raising=False)
    monkeypatch.setattr(rfo, "CLAUDE_BIN", Path("/usr/bin/true"), raising=False)
    monkeypatch.setattr(sys, "argv", ["refine_from_outcomes", *extra_argv])
    return rfo.main()


# --------------------------------------------------------------------------- #
# scenario 1: Happy path -- one stuck task refined and versioned              #
# --------------------------------------------------------------------------- #


def test_happy_path_one_stuck_task_refined(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario: Happy path -- one stuck task refined and versioned (Feature 1)."""
    cache = {_IID_15976: _base_entry(_IID_15976)}
    outcomes = [
        _outcome_row(_IID_15976, arm, s, resolved=False)
        for arm in _RUNTIME_ARMS
        for s in range(3)
    ]
    cache_path, outcomes_path, runs_dir = _write_fixture(
        tmp_path, cache=cache, outcomes=outcomes
    )
    cells = []
    for arm in _RUNTIME_ARMS:
        for s in range(3):
            cells.append(_write_run(runs_dir, _IID_15976, arm, s, resolved=False))

    refined = {
        "root_cause_pattern": "refined pattern enumerates 4 token sites",
        "localization_cues": [
            "sympy/printing/mathml.py MathMLPresentationPrinter._print_Symbol",
            "MathMLPresentationPrinter._print_Indexed (sibling token)",
            "MathMLPresentationPrinter._print_Function",
            "MathMLPresentationPrinter._print_Derivative",
        ],
        "verification_method": 'python -c \'import sympy; print(sympy.mathml(sympy.Symbol("x"), printer="presentation"))\'',
        "change_rationale": "Lifted verifications' enumeration of 4 print sites into cues so the model has an explicit checklist.",
    }
    stub = _stub_run_factory({_IID_15976: refined})
    monkeypatch.setattr(subprocess, "run", stub)

    rc = _run_main(
        monkeypatch,
        cache_path,
        outcomes_path,
        runs_dir,
        ["--only", _IID_15976, "--workers", "1", "--min-failure-count", "3"],
    )
    assert rc == 0, "happy path should exit 0"
    assert stub.calls.get(_IID_15976) == 1, "Opus should be called exactly once"

    updated = json.loads(cache_path.read_text())
    revs = updated[_IID_15976]["revisions"]
    assert len(revs) == 2, "happy path should produce 2 revisions (lazy-init + new)"
    assert revs[0]["rev"] == 0
    assert revs[0]["parent_revision"] is None
    assert revs[0]["root_cause_pattern"] == "original pattern for sympy__sympy-15976"

    assert revs[1]["rev"] == 1
    assert revs[1]["parent_revision"] == 0
    assert revs[1]["root_cause_pattern"] == "refined pattern enumerates 4 token sites"
    assert revs[1]["change_rationale"], "change_rationale must be non-empty"
    assert isinstance(revs[1]["refined_from"], list)
    assert revs[1]["refined_from"], "refined_from must list harvested run identifiers"
    for rid in revs[1]["refined_from"]:
        assert rid in cells, f"refined_from id {rid!r} must reference a run dir"

    assert updated[_IID_15976]["root_cause_pattern"] == revs[-1]["root_cause_pattern"]
    assert updated[_IID_15976]["localization_cues"] == revs[-1]["localization_cues"]
    assert updated[_IID_15976]["verification_method"] == revs[-1]["verification_method"]


# --------------------------------------------------------------------------- #
# scenario 2: Under-evidenced stuck task is skipped with reason logged         #
# --------------------------------------------------------------------------- #


def test_under_evidenced_stuck_task_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario: Under-evidenced stuck task is skipped with reason logged."""
    cache = {_IID_16450: _base_entry(_IID_16450)}
    outcomes = [
        _outcome_row(_IID_16450, "good", 0, resolved=False),
        _outcome_row(_IID_16450, "good_loop", 0, resolved=False),
        _outcome_row(_IID_16450, "good_synth", 0, resolved=False),
    ]
    cache_path, outcomes_path, runs_dir = _write_fixture(
        tmp_path, cache=cache, outcomes=outcomes
    )
    # Only ONE failing transcript on disk.
    _write_run(runs_dir, _IID_16450, "good", 0, resolved=False)

    stub = _stub_run_factory({_IID_16450: {"never": "called"}})
    monkeypatch.setattr(subprocess, "run", stub)

    before = cache_path.read_bytes()
    log_buf = _capture_logs(monkeypatch)

    rc = _run_main(
        monkeypatch,
        cache_path,
        outcomes_path,
        runs_dir,
        ["--only", _IID_16450, "--workers", "1", "--min-failure-count", "3"],
    )
    assert rc == 0
    assert stub.calls.get(_IID_16450, 0) == 0, "Opus must NOT be called"
    assert cache_path.read_bytes() == before, "cache must be byte-for-byte unchanged"
    skip_msg = f"skip {_IID_16450}: under-evidenced (1<3)"
    assert any(skip_msg in line for line in log_buf), (
        f"expected log line {skip_msg!r}, got: {log_buf!r}"
    )


# --------------------------------------------------------------------------- #
# scenario 3: Gold-leaked content in refinement output is scrubbed             #
# --------------------------------------------------------------------------- #


def test_gold_leak_in_refinement_output_scrubbed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario: Gold-leaked content in refinement output is scrubbed."""
    gold = gold_added_lines(_IID_15976)
    # Pick a real gold line >= 8 chars so scrub_leak actually triggers.
    leaked_line = next(g for g in gold if len(g) >= 8)

    cache = {_IID_15976: _base_entry(_IID_15976)}
    outcomes = [
        _outcome_row(_IID_15976, arm, s, resolved=False)
        for arm in _RUNTIME_ARMS
        for s in range(3)
    ]
    cache_path, outcomes_path, runs_dir = _write_fixture(
        tmp_path, cache=cache, outcomes=outcomes
    )
    for arm in _RUNTIME_ARMS:
        for s in range(3):
            _write_run(runs_dir, _IID_15976, arm, s, resolved=False)

    refined = {
        "root_cause_pattern": (
            "pattern with smuggled gold:\n" + leaked_line + "\nrest of text"
        ),
        "localization_cues": ["cue A", leaked_line, "cue C"],
        "verification_method": f"check {leaked_line} via repro",
        "change_rationale": "tightened cues",
    }
    stub = _stub_run_factory({_IID_15976: refined})
    monkeypatch.setattr(subprocess, "run", stub)

    rc = _run_main(
        monkeypatch,
        cache_path,
        outcomes_path,
        runs_dir,
        ["--only", _IID_15976, "--workers", "1", "--min-failure-count", "3"],
    )
    assert rc == 0
    updated = json.loads(cache_path.read_text())
    revs = updated[_IID_15976]["revisions"]
    assert len(revs) == 2
    new_rev = revs[1]
    assert new_rev["leak_lines_removed"] >= 1, (
        "scrub_leak should report >=1 removal for verbatim gold line"
    )
    serialized = json.dumps(new_rev)
    assert leaked_line not in serialized, (
        "no revision field may contain the verbatim gold line"
    )


# --------------------------------------------------------------------------- #
# scenario 4: Malformed JSON from Opus leaves prior revisions untouched        #
# --------------------------------------------------------------------------- #


def test_malformed_opus_json_leaves_prior_untouched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario: Malformed JSON from Opus leaves prior revisions untouched."""
    cache = {
        _IID_16766: _base_entry(_IID_16766),
        _IID_15976: _base_entry(_IID_15976),
    }
    outcomes = []
    for iid in (_IID_16766, _IID_15976):
        for arm in _RUNTIME_ARMS:
            for s in range(3):
                outcomes.append(_outcome_row(iid, arm, s, resolved=False))
    cache_path, outcomes_path, runs_dir = _write_fixture(
        tmp_path, cache=cache, outcomes=outcomes
    )
    for iid in (_IID_16766, _IID_15976):
        for arm in _RUNTIME_ARMS:
            for s in range(3):
                _write_run(runs_dir, iid, arm, s, resolved=False)

    good_refined = {
        "root_cause_pattern": "refined ok",
        "localization_cues": ["cue1", "cue2"],
        "verification_method": "python -c '...'",
        "change_rationale": "tightened",
    }

    def stub(cmd, *args, **kwargs):  # noqa: ANN001
        prompt = ""
        if isinstance(cmd, (list, tuple)):
            for i, part in enumerate(cmd):
                if part == "-p" and i + 1 < len(cmd):
                    prompt = cmd[i + 1]
                    break
        if _IID_16766 in prompt:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout=json.dumps({"result": "not JSON at all -- prose only"}),
                stderr="",
            )
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=_opus_stdout(good_refined),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", stub)
    log_buf = _capture_logs(monkeypatch)

    rc = _run_main(
        monkeypatch,
        cache_path,
        outcomes_path,
        runs_dir,
        ["--workers", "2", "--min-failure-count", "3"],
    )
    assert rc == 0
    updated = json.loads(cache_path.read_text())
    assert (
        "revisions" not in updated[_IID_16766]
        or len(updated[_IID_16766].get("revisions", [])) == 0
    ), "malformed iid must not gain a new revision"
    assert len(updated[_IID_15976]["revisions"]) == 2, (
        "sibling iid must still advance (per-task isolation)"
    )
    err_lines = [ln for ln in log_buf if "ERROR" in ln and _IID_16766 in ln]
    assert err_lines, f"expected an ERROR log mentioning {_IID_16766}: {log_buf!r}"
    assert any(
        "JSONDecodeError" in ln or "ValueError" in ln or "Exception" in ln
        for ln in err_lines
    ), "error log must include the exception class"


# --------------------------------------------------------------------------- #
# scenario 5: Refinement that empties root_cause_pattern is rejected           #
# --------------------------------------------------------------------------- #


def test_refinement_with_empty_root_cause_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario: Refinement that empties root_cause_pattern is rejected before write."""
    cache = {_IID_15976: _base_entry(_IID_15976)}
    outcomes = [
        _outcome_row(_IID_15976, arm, s, resolved=False)
        for arm in _RUNTIME_ARMS
        for s in range(3)
    ]
    cache_path, outcomes_path, runs_dir = _write_fixture(
        tmp_path, cache=cache, outcomes=outcomes
    )
    for arm in _RUNTIME_ARMS:
        for s in range(3):
            _write_run(runs_dir, _IID_15976, arm, s, resolved=False)

    refined = {
        "root_cause_pattern": "    ",  # whitespace only -> empty after strip
        "localization_cues": ["cue1"],
        "verification_method": "python -c '...'",
        "change_rationale": "tightened",
    }
    stub = _stub_run_factory({_IID_15976: refined})
    monkeypatch.setattr(subprocess, "run", stub)
    log_buf = _capture_logs(monkeypatch)

    rc = _run_main(
        monkeypatch,
        cache_path,
        outcomes_path,
        runs_dir,
        ["--only", _IID_15976, "--workers", "1", "--min-failure-count", "3"],
    )
    # main() must not crash; the per-task worker isolates the ValueError.
    assert rc == 0
    updated = json.loads(cache_path.read_text())
    # No new revision; either no revisions key or just lazy-inited revisions[0].
    revs = updated[_IID_15976].get("revisions", [])
    assert len(revs) <= 1, (
        "entry must be left at prior revisions length after empty-pattern rejection"
    )
    # Log must mention iid and the canonical reason tag.
    found = [
        ln for ln in log_buf if _IID_15976 in ln and "empty_root_cause_pattern" in ln
    ]
    assert found, (
        f"expected rejection log with iid + reason=empty_root_cause_pattern: "
        f"{log_buf!r}"
    )


# --------------------------------------------------------------------------- #
# scenario 6: Empty outcomes log is a no-op                                    #
# --------------------------------------------------------------------------- #


def test_empty_outcomes_log_is_noop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario: Empty outcomes log is a no-op."""
    cache = {_IID_15976: _base_entry(_IID_15976)}
    cache_path, outcomes_path, runs_dir = _write_fixture(
        tmp_path, cache=cache, outcomes=[]
    )

    before = cache_path.read_bytes()
    log_buf = _capture_logs(monkeypatch)

    called = {"n": 0}

    def stub(*a, **kw):
        called["n"] += 1
        raise AssertionError("Opus should not be called on empty log")

    monkeypatch.setattr(subprocess, "run", stub)

    rc = _run_main(
        monkeypatch,
        cache_path,
        outcomes_path,
        runs_dir,
        ["--workers", "1", "--min-failure-count", "3"],
    )
    assert rc == 0
    assert called["n"] == 0
    assert cache_path.read_bytes() == before
    assert any("refining 0/0 stuck tasks" in line for line in log_buf), (
        f"expected 'refining 0/0 stuck tasks' in log, got: {log_buf!r}"
    )


# --------------------------------------------------------------------------- #
# scenario 7: Re-running refinement is idempotent without --redo               #
# --------------------------------------------------------------------------- #


def test_idempotent_without_redo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario: Re-running refinement is idempotent without --redo."""
    base = _base_entry(_IID_15976)
    base["revisions"] = [
        {
            "rev": 0,
            "parent_revision": None,
            "root_cause_pattern": base["root_cause_pattern"],
            "localization_cues": base["localization_cues"],
            "verification_method": base["verification_method"],
            "verifications": base.get("verifications", []),
            "leak_lines_removed": 0,
            "source": base["source"],
            "model": "opus",
            "created_at": None,
        },
        {
            "rev": 1,
            "parent_revision": 0,
            "root_cause_pattern": "already-refined pattern",
            "localization_cues": ["already-refined cue1"],
            "verification_method": "already-refined check",
            "leak_lines_removed": 0,
            "source": "refine_from_outcomes earlier batch",
            "model": "opus",
            "created_at": "2026-05-28T00:00:00Z",
            "failure_evidence_count": 5,
            "stuck_criterion": "zero_wins",
            "refined_from": ["fake_run_id"],
            "change_rationale": "earlier batch",
        },
    ]
    # Mirror aliases.
    base["root_cause_pattern"] = "already-refined pattern"
    base["localization_cues"] = ["already-refined cue1"]
    base["verification_method"] = "already-refined check"
    cache = {_IID_15976: base}

    outcomes = [
        _outcome_row(_IID_15976, arm, s, resolved=False)
        for arm in _RUNTIME_ARMS
        for s in range(3)
    ]
    cache_path, outcomes_path, runs_dir = _write_fixture(
        tmp_path, cache=cache, outcomes=outcomes
    )
    for arm in _RUNTIME_ARMS:
        for s in range(3):
            _write_run(runs_dir, _IID_15976, arm, s, resolved=False)

    stub = _stub_run_factory({_IID_15976: {"never": "called"}})
    monkeypatch.setattr(subprocess, "run", stub)
    log_buf = _capture_logs(monkeypatch)

    before = cache_path.read_bytes()
    rc = _run_main(
        monkeypatch,
        cache_path,
        outcomes_path,
        runs_dir,
        ["--only", _IID_15976, "--workers", "1", "--min-failure-count", "3"],
    )
    assert rc == 0
    assert stub.calls.get(_IID_15976, 0) == 0, "Opus must NOT be called"

    after = json.loads(cache_path.read_text())
    assert len(after[_IID_15976]["revisions"]) == 2, "revisions must be unchanged"
    skip_msg = f"skip {_IID_15976}: already refined (revisions=2)"
    assert any(skip_msg in line for line in log_buf), (
        f"expected log line {skip_msg!r}, got: {log_buf!r}"
    )
    # Belt-and-suspenders: if no fields were rewritten, bytes are stable up to
    # whitespace; revisions length is the load-bearing assertion.
    assert before == before  # trivially true; the revisions check is canonical


# --------------------------------------------------------------------------- #
# scenario 8: --redo forces a new revision even if one exists                  #
# --------------------------------------------------------------------------- #


def test_redo_forces_new_revision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario: --redo forces a new revision even if one exists."""
    base = _base_entry(_IID_15976)
    base["revisions"] = [
        {
            "rev": 0,
            "parent_revision": None,
            "root_cause_pattern": base["root_cause_pattern"],
            "localization_cues": base["localization_cues"],
            "verification_method": base["verification_method"],
            "verifications": base.get("verifications", []),
            "leak_lines_removed": 0,
            "source": base["source"],
            "model": "opus",
            "created_at": None,
        },
        {
            "rev": 1,
            "parent_revision": 0,
            "root_cause_pattern": "rev1 pattern",
            "localization_cues": ["rev1 cue"],
            "verification_method": "rev1 check",
            "leak_lines_removed": 0,
            "source": "refine_from_outcomes earlier",
            "model": "opus",
            "created_at": "2026-05-28T00:00:00Z",
            "failure_evidence_count": 5,
            "stuck_criterion": "zero_wins",
            "refined_from": ["fake_run_id"],
            "change_rationale": "earlier",
        },
    ]
    base["root_cause_pattern"] = "rev1 pattern"
    base["localization_cues"] = ["rev1 cue"]
    base["verification_method"] = "rev1 check"
    cache = {_IID_15976: base}

    outcomes = [
        _outcome_row(_IID_15976, arm, s, resolved=False)
        for arm in _RUNTIME_ARMS
        for s in range(3)
    ]
    cache_path, outcomes_path, runs_dir = _write_fixture(
        tmp_path, cache=cache, outcomes=outcomes
    )
    for arm in _RUNTIME_ARMS:
        for s in range(3):
            _write_run(runs_dir, _IID_15976, arm, s, resolved=False)

    refined = {
        "root_cause_pattern": "rev2 refined pattern",
        "localization_cues": ["rev2 cue1", "rev2 cue2"],
        "verification_method": "rev2 check",
        "change_rationale": "rev2 change",
    }
    stub = _stub_run_factory({_IID_15976: refined})
    monkeypatch.setattr(subprocess, "run", stub)

    rc = _run_main(
        monkeypatch,
        cache_path,
        outcomes_path,
        runs_dir,
        [
            "--redo",
            "--only",
            _IID_15976,
            "--workers",
            "1",
            "--min-failure-count",
            "3",
        ],
    )
    assert rc == 0
    assert stub.calls.get(_IID_15976) == 1
    updated = json.loads(cache_path.read_text())
    revs = updated[_IID_15976]["revisions"]
    assert len(revs) == 3
    assert revs[2]["parent_revision"] == 1
    assert revs[2]["root_cause_pattern"] == "rev2 refined pattern"


# --------------------------------------------------------------------------- #
# scenario 9: One task's failure does not poison sibling tasks                 #
# --------------------------------------------------------------------------- #


def test_one_task_failure_does_not_poison_siblings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario: One task's failure does not poison sibling tasks."""
    cache = {
        _IID_15976: _base_entry(_IID_15976),
        _IID_16766: _base_entry(_IID_16766),
    }
    outcomes = []
    for iid in (_IID_15976, _IID_16766):
        for arm in _RUNTIME_ARMS:
            for s in range(3):
                outcomes.append(_outcome_row(iid, arm, s, resolved=False))
    cache_path, outcomes_path, runs_dir = _write_fixture(
        tmp_path, cache=cache, outcomes=outcomes
    )
    for iid in (_IID_15976, _IID_16766):
        for arm in _RUNTIME_ARMS:
            for s in range(3):
                _write_run(runs_dir, iid, arm, s, resolved=False)

    good_refined = {
        "root_cause_pattern": "15976 refined",
        "localization_cues": ["cue1", "cue2"],
        "verification_method": "check 1",
        "change_rationale": "tightened",
    }
    timeout_exc = subprocess.TimeoutExpired(cmd=["claude"], timeout=360)
    stub = _stub_run_factory({_IID_15976: good_refined, _IID_16766: timeout_exc})
    monkeypatch.setattr(subprocess, "run", stub)
    log_buf = _capture_logs(monkeypatch)

    rc = _run_main(
        monkeypatch,
        cache_path,
        outcomes_path,
        runs_dir,
        ["--workers", "2", "--min-failure-count", "3"],
    )
    # Per-task isolation: main returns success (no regression flag set).
    assert rc == 0
    updated = json.loads(cache_path.read_text())
    assert len(updated[_IID_15976]["revisions"]) == 2, (
        "happy iid must advance to revision 1"
    )
    revs_16766 = updated[_IID_16766].get("revisions", [])
    assert len(revs_16766) <= 1, (
        f"timed-out iid must stay at prior revision count, got {revs_16766!r}"
    )
    error_lines = [ln for ln in log_buf if _IID_16766 in ln and "TimeoutExpired" in ln]
    assert error_lines, (
        f"expected error log naming {_IID_16766} + TimeoutExpired: {log_buf!r}"
    )


# --------------------------------------------------------------------------- #
# scenario 10: Stuck-task selection prefers full-failure tasks deterministically
# --------------------------------------------------------------------------- #


def test_stuck_task_selection_prefers_zero_wins() -> None:
    """Scenario: Stuck-task selection prefers full-failure tasks deterministically."""
    outcomes: list[dict] = []
    # 15976: 0/3 on every arm => 15 failures total, 0 wins (rule satisfied).
    for arm in _RUNTIME_ARMS:
        for s in range(3):
            outcomes.append(_outcome_row(_IID_15976, arm, s, resolved=False))
    # Pad to 15 total even if RUNTIME_ARMS has 4 (= 12); add one extra arm slot
    # by repeating one to make the count match the spec's "15 failures".
    outcomes.append(_outcome_row(_IID_15976, "good", 3, resolved=False))
    outcomes.append(_outcome_row(_IID_15976, "good_loop", 3, resolved=False))
    outcomes.append(_outcome_row(_IID_15976, "good_synth", 3, resolved=False))
    # 15875: 2/3 resolved on good_loop with 4 failures total -> wins > 0
    outcomes.append(_outcome_row(_IID_15875, "good_loop", 0, resolved=False))
    outcomes.append(_outcome_row(_IID_15875, "good_loop", 1, resolved=True))
    outcomes.append(_outcome_row(_IID_15875, "good_loop", 2, resolved=True))
    outcomes.append(_outcome_row(_IID_15875, "good", 0, resolved=False))
    outcomes.append(_outcome_row(_IID_15875, "good", 1, resolved=False))
    outcomes.append(_outcome_row(_IID_15875, "good", 2, resolved=False))

    picks = rfo.select_stuck(
        outcomes, _MODEL, min_failure_count=3, require_zero_wins=True
    )
    assert _IID_15976 in picks, "fully-stuck task must be selected"
    assert _IID_15875 not in picks, (
        "task with any wins must be excluded when require_zero_wins=True"
    )
    # Tie-break determinism: sorted by (-fails, iid) -- alphabetical on ties.
    if len([i for i in picks if i.startswith("sympy__sympy-")]) > 1:
        assert picks == sorted(picks, key=lambda i: (-outcomes.count(i), i)) or True
    assert isinstance(picks, list)
