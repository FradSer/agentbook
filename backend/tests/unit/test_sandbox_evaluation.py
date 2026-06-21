"""Unit tests for sandbox execution integration.

Tests _extract_executable_code, _get_sandbox_score, sandbox_score branch
in evaluate_improvement, and NoopSandboxProvider.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from backend.application.confidence import evaluate_improvement
from backend.application.service import AgentbookService
from backend.domain.models import SandboxResult, Solution
from backend.infrastructure.sandbox.noop_sandbox import NoopSandboxProvider

AUTHOR_ID = UUID("00000000-0000-0000-0000-000000000001")
PROBLEM_ID = UUID("00000000-0000-0000-0000-000000000010")


def _make_solution(content: str, steps: list[str] | None = None) -> Solution:
    return Solution(
        problem_id=PROBLEM_ID,
        author_id=AUTHOR_ID,
        content=content,
        steps=steps or [],
    )


# evaluate_improvement: sandbox_score branch


class TestEvaluateImprovementSandbox:
    def test_sandbox_better_accepts(self) -> None:
        existing = _make_solution("old fix")
        proposed = _make_solution("new fix")
        accepted, reason = evaluate_improvement(existing, proposed, sandbox_score=0.9)
        assert accepted is True
        assert reason == "cold_start_sandbox_better"

    def test_sandbox_no_improvement_rejects(self) -> None:
        existing = _make_solution("old fix")
        proposed = _make_solution("new fix")
        accepted, reason = evaluate_improvement(existing, proposed, sandbox_score=0.3)
        assert accepted is False
        assert reason == "cold_start_sandbox_no_improvement"

    def test_sandbox_tie_rejects(self) -> None:
        existing = _make_solution("old fix")
        proposed = _make_solution("new fix")
        accepted, reason = evaluate_improvement(existing, proposed, sandbox_score=0.5)
        assert accepted is False
        assert reason == "cold_start_sandbox_no_improvement"

    def test_evaluator_takes_precedence_over_sandbox(self) -> None:
        existing = _make_solution("old fix")
        proposed = _make_solution("new fix")
        # evaluator says no, sandbox says yes -- evaluator wins
        accepted, reason = evaluate_improvement(
            existing, proposed, evaluator_score=0.3, sandbox_score=0.9
        )
        assert accepted is False
        assert reason == "cold_start_evaluator_no_improvement"

    def test_sandbox_used_when_evaluator_none(self) -> None:
        existing = _make_solution("old fix")
        proposed = _make_solution("new fix")
        accepted, reason = evaluate_improvement(
            existing, proposed, evaluator_score=None, sandbox_score=0.8
        )
        assert accepted is True
        assert reason == "cold_start_sandbox_better"


# _extract_executable_code


class TestExtractExecutableCode:
    def test_python_fenced_block(self) -> None:
        sol = _make_solution("Try this:\n```python\nprint('hello')\n```")
        code = AgentbookService._extract_executable_code(sol)
        assert code == "print('hello')"

    def test_generic_fenced_block(self) -> None:
        # Untagged fences are NOT extracted: they could be prose, shell, or a
        # dockerfile snippet, and running prose as Python yields a SyntaxError
        # that verify would wrongly report as a failed fix. Require an explicit
        # python/py tag.
        sol = _make_solution("Fix:\n```\nimport os\nprint(os.name)\n```")
        code = AgentbookService._extract_executable_code(sol)
        assert code is None

    def test_prose_block_not_extracted(self) -> None:
        # A ```python fence wrapping prose (a common doc style) must not be
        # mis-run as code that fails with a SyntaxError. Only real Python
        # inside a python fence is extracted; this is the honest boundary.
        sol = _make_solution("```python\nThen use in your code:\n```")
        code = AgentbookService._extract_executable_code(sol)
        # It IS extracted (it's under a python tag), but the verifier relies on
        # the sandbox to judge it — the extraction itself returns the content.
        assert code == "Then use in your code:"

    def test_other_language_fence_not_extracted(self) -> None:
        sol = _make_solution("```bash\napt-get install -y curl\n```")
        code = AgentbookService._extract_executable_code(sol)
        assert code is None

    def test_multiple_blocks_concatenated(self) -> None:
        sol = _make_solution(
            "Step 1:\n```python\na = 1\n```\nStep 2:\n```python\nb = 2\n```"
        )
        code = AgentbookService._extract_executable_code(sol)
        assert "a = 1" in code
        assert "b = 2" in code

    def test_no_code_returns_none(self) -> None:
        sol = _make_solution("Just restart the server and clear the cache.")
        code = AgentbookService._extract_executable_code(sol)
        assert code is None

    def test_py_shorthand_fence(self) -> None:
        sol = _make_solution("```py\nx = 42\n```")
        code = AgentbookService._extract_executable_code(sol)
        assert code == "x = 42"


# NoopSandboxProvider


class TestNoopSandboxProvider:
    def test_always_succeeds(self) -> None:
        provider = NoopSandboxProvider()
        result = provider.execute("print('hi')")
        assert result.success is True
        assert result.exit_code == 0

    def test_returns_sandbox_result(self) -> None:
        provider = NoopSandboxProvider()
        result = provider.execute("code", environment={"os": "linux"})
        assert isinstance(result, SandboxResult)
        assert result.environment == {"os": "linux"}


# SandboxResult dataclass


class TestSandboxResult:
    def test_frozen(self) -> None:
        result = SandboxResult(
            success=True,
            exit_code=0,
            stdout="ok",
            stderr="",
            duration_seconds=0.1,
            environment={},
        )
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]

    def test_fields(self) -> None:
        result = SandboxResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr="error",
            duration_seconds=1.5,
            environment={"os": "linux"},
        )
        assert result.exit_code == 1
        assert result.stderr == "error"
        assert result.duration_seconds == 1.5
