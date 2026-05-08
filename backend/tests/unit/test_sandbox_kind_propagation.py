"""Verification: sandbox-driven outcomes must be tagged kind="verified".

This test was added to verify a bug surfaced by the agent-team reflection on
2026-05-08: the sandbox auto-evaluation path (``_run_sandbox_evaluation``)
records outcomes via ``_record_synthetic_outcome``, which constructs
``Outcome(...)`` without passing ``kind``. The dataclass default is
``"observed"`` (``backend/domain/models.py:108``). The Bayesian scorer
applies the 2x ``kind_multiplier`` only when ``kind == "verified"``
(``backend/application/confidence.py:31``).

Net effect on current code:
  * ``outcome.kind == "observed"`` (should be "verified")
  * ``outcome.weight == 0.3``      (should be 1.0)
  * ``kind_multiplier == 1.0``     (should be 2.0)

A sandbox PASS therefore contributes ~0.3 final-weight when it should
contribute ~2.0 — about 6.7x undervalued. This silently nullifies the
sandbox-primary lever the platform's principles document points operators
at as the highest-value gap to close.

The path that DOES tag correctly is ``report_outcome`` (service.py:1252),
but ``_run_sandbox_evaluation`` does not call it — it calls
``_record_synthetic_outcome`` directly.

Once the fix lands (passing ``kind="verified", weight=1.0`` through
``_record_synthetic_outcome``), this file becomes the regression guard.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from backend.application.service import SANDBOX_AGENT_ID
from backend.domain.models import Problem, SandboxResult, Solution
from backend.tests.conftest import _build_service


class _AlwaysSucceedSandbox:
    """SandboxProvider stub returning a successful run for any code."""

    def execute(
        self,
        code: str,
        error_signature: str | None = None,
        timeout_seconds: int = 30,
        environment: dict | None = None,
    ) -> SandboxResult:
        return SandboxResult(
            success=True,
            exit_code=0,
            stdout="ok",
            stderr="",
            duration_seconds=0.05,
            environment=environment or {},
        )


def _seed_problem_with_executable_solution(
    service, author_id: UUID
) -> tuple[Problem, Solution]:
    """Create a problem + solution; the solution's content carries a
    fenced Python block so ``_extract_executable_code`` returns code."""
    problem = Problem(
        author_id=author_id,
        description="reproducer for KeyError on missing dict key",
        error_signature="KeyError: 'x'",
        review_status="approved",
    )
    service._problems.add(problem)

    solution = Solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content=(
            "Use ``.get`` instead of ``[]`` to avoid the KeyError:\n\n"
            "```python\n"
            "data = {}\n"
            "value = data.get('x')\n"
            "assert value is None\n"
            "```\n"
        ),
        steps=["Use .get for safe lookup", "Validate result is not None"],
        review_status="approved",
    )
    service._solutions.add(solution)
    return problem, solution


def test_sandbox_evaluation_records_verified_kind() -> None:
    """A sandbox PASS must be recorded as ``kind="verified"``.

    Currently fails: the outcome lands as ``kind="observed"`` because
    ``_record_synthetic_outcome`` doesn't propagate ``kind``. This is the
    exact bug the agent-team reflection identified and the user asked to
    verify.
    """
    service, author_id = _build_service(with_sandbox=_AlwaysSucceedSandbox())
    problem, solution = _seed_problem_with_executable_solution(service, author_id)

    service._run_sandbox_evaluation(problem, solution, agent_id=author_id)

    recorded = service._outcomes.list_by_solution(solution.solution_id)
    assert len(recorded) == 1, (
        f"sandbox eval should record exactly one outcome, got {len(recorded)}"
    )
    outcome = recorded[0]
    assert outcome.reporter_id == SANDBOX_AGENT_ID
    assert outcome.success is True

    # The bug: kind is currently "observed". When fixed it must be "verified".
    assert outcome.kind == "verified", (
        f"expected kind='verified' for sandbox auto-eval, got {outcome.kind!r}. "
        f"This is the verified-vs-observed propagation bug — sandbox outcomes "
        f"are slipping through as observed and missing the 2x kind_multiplier."
    )


def test_sandbox_evaluation_records_full_weight() -> None:
    """A sandbox PASS must carry weight=1.0, not 0.3.

    The 0.3 default in ``_record_synthetic_outcome`` was calibrated for the
    LLM A/B evaluator (synthetic, weak signal). The sandbox is ground-truth
    execution and deserves full weight. The current code applies 0.3
    universally to anything routed through ``_record_synthetic_outcome``.
    """
    service, author_id = _build_service(with_sandbox=_AlwaysSucceedSandbox())
    problem, solution = _seed_problem_with_executable_solution(service, author_id)

    service._run_sandbox_evaluation(problem, solution, agent_id=author_id)

    outcome = service._outcomes.list_by_solution(solution.solution_id)[0]
    assert outcome.weight == 1.0, (
        f"expected sandbox outcome weight=1.0 (ground truth), got {outcome.weight}. "
        f"The shared _record_synthetic_outcome helper defaults to 0.3 "
        f"(LLM-evaluator weight) and the sandbox call site does not override."
    )


@pytest.mark.parametrize(
    "field,expected,actual_now",
    [
        ("kind", "verified", "observed"),
        ("weight", 1.0, 0.3),
    ],
)
def test_sandbox_kind_and_weight_documented_failure_modes(
    field, expected, actual_now
) -> None:
    """Document the two-axis bug shape — kind AND weight, both wrong.

    This test runs the sandbox path and asserts the EXPECTED post-fix
    values. It will fail in two distinct ways on current code, naming
    each failure mode for clarity.
    """
    service, author_id = _build_service(with_sandbox=_AlwaysSucceedSandbox())
    problem, solution = _seed_problem_with_executable_solution(service, author_id)
    service._run_sandbox_evaluation(problem, solution, agent_id=author_id)
    outcome = service._outcomes.list_by_solution(solution.solution_id)[0]
    assert getattr(outcome, field) == expected, (
        f"sandbox outcome.{field}: expected {expected!r}, got "
        f"{getattr(outcome, field)!r} — bug currently produces {actual_now!r}"
    )


# ---------------------------------------------------------------------------
# Sibling regression guard: the LLM A/B evaluator path must STAY observed/0.3
# ---------------------------------------------------------------------------
#
# The sandbox fix above explicitly overrides ``kind="verified", weight=1.0``
# at the call site. The shared helper ``_record_synthetic_outcome`` keeps
# its defaults (``kind="observed"``, ``weight=0.3``) for the LLM A/B
# evaluator path, which is a weak / synthetic signal and must NOT pick up
# the 2x kind_multiplier. If a future refactor "tidies up" the helper's
# defaults to ``kind="verified"`` (because "we always want verified"), the
# evaluator path would silently start producing verified-tagged outcomes
# from LLM judgments — exactly the inverse of the inflated-confidence
# 2026-04-01 post-mortem failure mode. These tests pin the contract.


class _AlwaysPreferProposedEvaluator:
    """EvaluatorProvider stub returning a fixed score > 0.5."""

    def compare(
        self,
        problem_description: str,
        solution_a: str,
        solution_b: str,
    ) -> float:
        return 0.8


def _seed_problem_with_two_solutions(service, author_id):
    """Create one approved problem + two approved solutions; return ids."""
    from backend.domain.models import Problem, Solution

    problem = Problem(
        author_id=author_id,
        description="reproducer for KeyError on missing dict key",
        error_signature="KeyError: 'x'",
        review_status="approved",
    )
    service._problems.add(problem)
    existing = Solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Use ``data.get('x')`` to avoid the KeyError.",
        review_status="approved",
    )
    proposed = Solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Use a try/except KeyError block to fall back gracefully.",
        review_status="approved",
    )
    service._solutions.add(existing)
    service._solutions.add(proposed)
    return problem, existing, proposed


def test_llm_evaluator_path_records_observed_kind() -> None:
    """The LLM A/B evaluator path must record ``kind="observed"``.

    Symmetric to ``test_sandbox_evaluation_records_verified_kind``: this
    guards against the OPPOSITE drift (helper defaults flipped to
    ``"verified"`` so synthetic LLM judgments pick up 2x weight).
    """
    service, author_id = _build_service(with_evaluator=_AlwaysPreferProposedEvaluator())
    problem, existing, proposed = _seed_problem_with_two_solutions(service, author_id)

    service._run_llm_evaluation(problem, existing, proposed)

    recorded = service._outcomes.list_by_solution(proposed.solution_id)
    assert len(recorded) == 1
    outcome = recorded[0]
    assert outcome.kind == "observed", (
        f"expected LLM A/B evaluator outcome.kind='observed' (synthetic "
        f"weak signal), got {outcome.kind!r}. If this flipped to "
        f"'verified' the 2x kind_multiplier in confidence.calculate_"
        f"confidence will fire on every LLM judgment — the inverse of "
        f"the sandbox fix at service.py:2146."
    )


def test_llm_evaluator_path_records_default_weight() -> None:
    """The LLM A/B evaluator path must record ``weight=0.3``.

    The helper default is intentionally low because LLM judgment is a
    proxy, not ground truth. Sandbox runs override to 1.0; LLM runs do
    not, and must keep the 0.3 calibration.
    """
    service, author_id = _build_service(with_evaluator=_AlwaysPreferProposedEvaluator())
    problem, existing, proposed = _seed_problem_with_two_solutions(service, author_id)

    service._run_llm_evaluation(problem, existing, proposed)

    outcome = service._outcomes.list_by_solution(proposed.solution_id)[0]
    assert outcome.weight == 0.3, (
        f"expected LLM A/B evaluator outcome.weight=0.3 (calibrated low "
        f"for synthetic signal), got {outcome.weight}. The shared helper "
        f"_record_synthetic_outcome's default must not drift; the "
        f"sandbox path overrides to 1.0 at the call site."
    )
