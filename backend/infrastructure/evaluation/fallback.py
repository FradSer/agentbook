from __future__ import annotations


class FallbackEvaluatorProvider:
    """No-op evaluator that always returns 0.5 (no preference).

    Used in tests and when no LLM API key is configured.
    """

    def compare(
        self,
        problem_description: str,
        solution_a: str,
        solution_b: str,
    ) -> float:
        return 0.5
