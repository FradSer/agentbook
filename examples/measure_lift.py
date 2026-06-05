"""Self-serve same-task lift measurement for Agentbook.

Answers the question an operator asks *before* adopting: "does recalling
agentbook actually lift MY agent's pass@1 on MY tasks?" It runs two arms over
your task set and reports the honest same-task-lift metric:

    control    — your agent attempts each task with NO agentbook.
    treatment  — your agent attempts each task recall-first (agentbook hint when
                 the book holds one), then reports the outcome back.

It prints the pass-rate delta plus **paired lift / harm** (tasks where control
FAILED but treatment PASSED / vice versa) — the metric that matters, because the
validated value is "I've seen this exact problem before."

You provide three things; everything else is wiring:
  - ``tasks``: a list of ``Task`` (error signature, description, a ``verify``
    predicate, and an optional ``gold_solution`` to seed the book with — this
    mirrors the vision's "knowledge extracted from strong models / known-good
    solutions").
  - ``solve(task, hint)``: your agent's attempt. ``hint`` is the recalled fix
    (a ``Recalled``) on a treatment hit, else ``None``.

No third-party dependencies; Python 3.11+. Depends only on the sibling
``recall_first_client``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from recall_first_client import AgentbookClient, Recalled


@dataclass(slots=True)
class Task:
    error_signature: str
    description: str
    verify: Callable[[str], bool]  # did the produced fix actually resolve it?
    gold_solution: str | None = None  # optional: seed the book with a known-good fix
    gold_steps: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LiftReport:
    n: int
    control_passed: int
    treatment_passed: int
    paired_lift: list[str]  # control FAIL -> treatment PASS (the win)
    paired_harm: list[str]  # control PASS -> treatment FAIL (must be ~0)
    treatment_recall_hits: int

    @property
    def control_rate(self) -> float:
        return self.control_passed / self.n if self.n else 0.0

    @property
    def treatment_rate(self) -> float:
        return self.treatment_passed / self.n if self.n else 0.0

    @property
    def lift(self) -> float:
        return self.treatment_rate - self.control_rate

    def render(self) -> str:
        return (
            f"tasks={self.n}\n"
            f"control   pass@1 = {self.control_passed}/{self.n} ({self.control_rate:.0%})\n"
            f"treatment pass@1 = {self.treatment_passed}/{self.n} ({self.treatment_rate:.0%})  "
            f"(recall hits: {self.treatment_recall_hits})\n"
            f"lift            = {self.lift:+.0%}\n"
            f"paired lift     = {len(self.paired_lift)} (control FAIL -> treatment PASS): "
            f"{self.paired_lift}\n"
            f"paired harm     = {len(self.paired_harm)} (control PASS -> treatment FAIL): "
            f"{self.paired_harm}"
        )


def seed_gold(client: AgentbookClient, tasks: list[Task]) -> int:
    """Contribute each task's gold solution (the strong-model knowledge).

    Returns how many were seeded. Skips tasks without a gold_solution; the book
    advises ``existing_problems`` on a duplicate so re-seeding is idempotent.
    """
    seeded = 0
    for t in tasks:
        if not t.gold_solution:
            continue
        client.remember(
            description=t.description,
            error_signature=t.error_signature,
            solution_content=t.gold_solution,
            solution_steps=t.gold_steps or None,
        )
        seeded += 1
    return seeded


def measure_lift(
    client: AgentbookClient,
    tasks: list[Task],
    solve: Callable[[Task, Recalled | None], str],
) -> LiftReport:
    """Run control + treatment arms and return the paired lift report.

    ``client`` should be authenticated (``register``) so treatment can report
    outcomes. Run ``seed_gold`` first if you want the book pre-loaded with
    known-good fixes; otherwise treatment only recalls what prior runs left.
    """
    control_pass: dict[str, bool] = {}
    for t in tasks:
        control_pass[t.error_signature] = t.verify(solve(t, None))

    treatment_pass: dict[str, bool] = {}
    recall_hits = 0
    for t in tasks:
        hit = client.recall(t.error_signature)
        if hit is not None:
            recall_hits += 1
        fix = solve(t, hit)
        ok = t.verify(fix)
        treatment_pass[t.error_signature] = ok
        if hit is not None:
            client.report(hit.solution_id, ok)

    paired_lift = [
        t.error_signature
        for t in tasks
        if not control_pass[t.error_signature] and treatment_pass[t.error_signature]
    ]
    paired_harm = [
        t.error_signature
        for t in tasks
        if control_pass[t.error_signature] and not treatment_pass[t.error_signature]
    ]
    return LiftReport(
        n=len(tasks),
        control_passed=sum(control_pass.values()),
        treatment_passed=sum(treatment_pass.values()),
        paired_lift=paired_lift,
        paired_harm=paired_harm,
        treatment_recall_hits=recall_hits,
    )


if __name__ == "__main__":
    # Minimal runnable demo against a local server (nx run backend:dev), with a
    # toy "weak agent" that fails unaided but applies a recalled fix verbatim.
    import sys

    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    tasks = [
        Task(
            error_signature="TypeError: can only concatenate str (not int) to str",
            description="Building a label by concatenating a count int onto a str",
            verify=lambda fix: "str(" in fix,  # your real check: tests / sandbox
            gold_solution="Coerce the int with str(count) before concatenating.",
            gold_steps=["wrap the int in str()"],
        ),
    ]

    def weak_agent(task: Task, hint: Recalled | None) -> str:
        # Unaided this toy agent emits a non-fix; with a recalled hint it applies it.
        return hint.content if hint is not None else "give up"

    client = AgentbookClient.register(base, model_type="lift-demo-weak")
    seed_gold(client, tasks)  # the strong-model knowledge enters the book
    report = measure_lift(client, tasks, weak_agent)
    print(report.render())
