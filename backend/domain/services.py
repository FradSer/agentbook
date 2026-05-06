from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from backend.domain.models import SandboxResult


class EmbeddingProvider(Protocol):
    def embed(self, text: str, *, input_type: str = "query") -> list[float]:
        """Generate embedding vector for input text.

        ``input_type`` lets asymmetric encoders (Voyage v3-large, Cohere
        embed-v4) pick the correct pole — ``"query"`` for live search,
        ``"document"`` for indexing. Symmetric providers (OpenRouter
        text-embedding-3-small, the deterministic Fallback) accept and ignore
        the kwarg so the call site stays uniform.
        """


# Cross-encoder reranker contract. ``RerankFn`` reorders a list of candidate
# documents against the query and returns indices into the input, sorted
# by relevance descending. Implementations must tolerate upstream failures:
# return identity ordering on rate-limit / 429 / SDK error rather than
# raising. The search path stays correct without rerank — Phase 1 scoring
# already eliminates the 27% high-confidence false positives.
RerankFn = Callable[[str, list[str], int], list[int]]
__all__ = ["EmbeddingProvider", "EvaluatorProvider", "RerankFn", "SandboxProvider"]


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
