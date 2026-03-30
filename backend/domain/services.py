from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]:
        """Generate embedding vector for input text."""


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
