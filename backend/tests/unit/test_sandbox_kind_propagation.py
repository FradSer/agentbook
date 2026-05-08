"""Regression guards on the contract between ``_record_synthetic_outcome``
and the Bayesian scorer's ``kind_multiplier``.

Sandbox-driven outcomes must carry ``kind="verified", weight=1.0`` so the
2x kind_multiplier in ``confidence.calculate_confidence`` fires for ground
truth. The LLM A/B evaluator path must keep the helper defaults
(``kind="observed", weight=0.3``) so synthetic judgments stay weak.
Both directions are pinned because either drift silently warps confidence.
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


@pytest.mark.parametrize(
    "field,expected",
    [("kind", "verified"), ("weight", 1.0), ("reporter_id", SANDBOX_AGENT_ID)],
)
def test_sandbox_evaluation_records_verified_outcome(field, expected) -> None:
    """Sandbox PASS records ``kind="verified", weight=1.0`` from ``SANDBOX_AGENT_ID``."""
    service, author_id = _build_service(with_sandbox=_AlwaysSucceedSandbox())
    problem, solution = _seed_problem_with_executable_solution(service, author_id)
    service._run_sandbox_evaluation(problem, solution, agent_id=author_id)
    recorded = service._outcomes.list_by_solution(solution.solution_id)
    assert len(recorded) == 1
    assert getattr(recorded[0], field) == expected


# LLM A/B evaluator path: opposite-direction guard. The helper defaults
# (``kind="observed", weight=0.3``) keep synthetic LLM judgments weak.
# A future "tidy the defaults to verified" refactor would silently pick
# up the 2x kind_multiplier — exactly the inverse of the sandbox bug.


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
    """Create one approved problem + two approved solutions."""
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


@pytest.mark.parametrize("field,expected", [("kind", "observed"), ("weight", 0.3)])
def test_llm_evaluator_path_keeps_default_observed(field, expected) -> None:
    """LLM A/B path keeps the helper defaults — guards against drift."""
    service, author_id = _build_service(with_evaluator=_AlwaysPreferProposedEvaluator())
    problem, existing, proposed = _seed_problem_with_two_solutions(service, author_id)
    service._run_llm_evaluation(problem, existing, proposed)
    recorded = service._outcomes.list_by_solution(proposed.solution_id)
    assert len(recorded) == 1
    assert getattr(recorded[0], field) == expected
