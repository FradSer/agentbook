from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from backend.domain.models import SandboxResult


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]:
        """Generate embedding vector for input text."""


class SandboxProvider(Protocol):
    def execute(
        self,
        code: str,
        error_signature: str | None = None,
        timeout_seconds: int = 30,
        environment: dict | None = None,
    ) -> SandboxResult:
        """Execute code in an isolated sandbox and return the result."""


class EvaluatorProvider(Protocol):
    def compare(
        self,
        problem_description: str,
        solution_a: str,
        solution_b: str,
    ) -> float:
        """A/B comparison of two solutions for a given problem.

        Returns probability that solution_b is better than solution_a.
        > 0.5 = B preferred, < 0.5 = A preferred, 0.5 = tie.
        """
