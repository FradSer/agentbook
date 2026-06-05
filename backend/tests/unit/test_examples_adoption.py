"""Regression tests for the adoption examples (examples/).

The reference recall-first client and the lift-measurement harness are product
surface now — if the API contract or their loop logic drifts they would rot
silently. These tests pin the *logic* (loop branching, paired lift/harm math)
with a fake client double — no HTTP, no server. End-to-end behaviour against a
live server is verified separately.
"""

from __future__ import annotations

import sys
from pathlib import Path

_EXAMPLES = Path(__file__).resolve().parents[3] / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from measure_lift import Task, measure_lift  # noqa: E402
from recall_first_client import AgentbookClient, Recalled  # noqa: E402


def _recalled(sid: str = "s1") -> Recalled:
    return Recalled(
        problem_id="p",
        solution_id=sid,
        content="fix",
        steps=[],
        confidence=0.9,
        match_quality="exact",
        root_cause_pattern=None,
        localization_cues=[],
        verification=[],
    )


class _FakeClient(AgentbookClient):
    """AgentbookClient with the three contract verbs stubbed (no network)."""

    def __init__(self, recall_returns: dict[str, Recalled | None]) -> None:
        super().__init__("http://fake", api_key="ak_test")
        self._recall_returns = recall_returns
        self.calls: list[tuple] = []

    def recall(self, error_signature: str, *, limit: int = 5) -> Recalled | None:
        self.calls.append(("recall", error_signature))
        return self._recall_returns.get(error_signature)

    def remember(self, **kwargs) -> dict:
        self.calls.append(("remember", kwargs.get("error_signature")))
        return {"problem_id": "p-new", "solution_id": "s-new"}

    def report(
        self, solution_id: str, success: bool, *, notes: str | None = None
    ) -> dict:
        self.calls.append(("report", solution_id, success))
        return {}


# --- recall_first loop branching --------------------------------------------


def test_recall_first_hit_uses_and_reports_without_contributing():
    c = _FakeClient({"E": _recalled("s1")})
    r = c.recall_first(
        error_signature="E",
        description="d",
        solve=lambda hint: hint.content,
        verify=lambda fix: True,
    )
    assert r.source == "recall" and r.success and r.solution_id == "s1"
    assert ("report", "s1", True) in c.calls
    assert not any(call[0] == "remember" for call in c.calls)


def test_recall_first_miss_solves_contributes_and_reports():
    c = _FakeClient({})  # recall returns None -> miss
    seen: dict = {}
    r = c.recall_first(
        error_signature="E",
        description="d",
        solve=lambda hint: seen.update(hint=hint) or "myfix",
        verify=lambda fix: True,
    )
    assert r.source == "solved" and r.success and r.solution_id == "s-new"
    assert seen["hint"] is None, "on a miss, solve() must be called with hint=None"
    assert ("remember", "E") in c.calls
    assert ("report", "s-new", True) in c.calls


def test_recall_first_miss_unsolved_neither_contributes_nor_reports():
    c = _FakeClient({})
    r = c.recall_first(
        error_signature="E",
        description="d",
        solve=lambda hint: "bad",
        verify=lambda fix: False,
    )
    assert r.source == "solved" and not r.success and r.solution_id is None
    assert not any(call[0] in ("remember", "report") for call in c.calls)


def test_recall_first_hit_reports_failure_when_recalled_fix_does_not_work():
    c = _FakeClient({"E": _recalled("s1")})
    r = c.recall_first(
        error_signature="E",
        description="d",
        solve=lambda hint: hint.content,
        verify=lambda fix: False,
    )
    assert r.source == "recall" and not r.success
    assert ("report", "s1", False) in c.calls


# --- measure_lift paired metrics --------------------------------------------


def test_measure_lift_reports_paired_lift_and_zero_harm():
    # E1 has a recallable fix; E2 does not. Control never passes; treatment
    # passes only where a recalled hint is applied -> paired lift on E1, no harm.
    c = _FakeClient({"E1": _recalled("s1")})
    tasks = [
        Task("E1", "d1", verify=lambda fix: fix == "fix"),
        Task("E2", "d2", verify=lambda fix: fix == "fix"),
    ]
    rep = measure_lift(
        c, tasks, solve=lambda task, hint: hint.content if hint else "nope"
    )
    assert rep.n == 2
    assert rep.control_passed == 0
    assert rep.treatment_passed == 1
    assert rep.treatment_recall_hits == 1
    assert rep.paired_lift == ["E1"]
    assert rep.paired_harm == []
    assert rep.lift == 0.5


def test_measure_lift_flags_harm_when_recall_regresses_a_passing_task():
    # Control passes E1; a (bad) recalled hint makes treatment fail -> harm.
    c = _FakeClient({"E1": _recalled("s1")})
    tasks = [Task("E1", "d1", verify=lambda fix: fix == "good")]
    # control (hint None) -> "good" (passes); treatment applies recalled "fix" (fails)
    rep = measure_lift(
        c, tasks, solve=lambda task, hint: hint.content if hint else "good"
    )
    assert rep.control_passed == 1
    assert rep.treatment_passed == 0
    assert rep.paired_harm == ["E1"]
    assert rep.paired_lift == []
