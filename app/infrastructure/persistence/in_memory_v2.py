from __future__ import annotations

import math
from datetime import datetime
from uuid import UUID

from app.domain.models import Outcome, Problem, Solution


def _cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    if not vector_a or not vector_b or len(vector_a) != len(vector_b):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vector_a, vector_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


class InMemoryProblemRepository:
    def __init__(self) -> None:
        self._problems: dict[UUID, Problem] = {}

    def add(self, problem: Problem) -> None:
        self._problems[problem.problem_id] = problem

    def get(self, problem_id: UUID) -> Problem | None:
        return self._problems.get(problem_id)

    def list_all(self) -> list[Problem]:
        return list(self._problems.values())

    def find_similar(self, embedding: list[float], threshold: float) -> list[Problem]:
        results: list[Problem] = []
        for problem in self._problems.values():
            if problem.embedding is None:
                continue
            similarity = _cosine_similarity(embedding, problem.embedding)
            if similarity >= threshold:
                results.append(problem)
        return results

    def find_by_error_signature(self, signature: str) -> Problem | None:
        for problem in self._problems.values():
            if problem.error_signature == signature:
                return problem
        return None

    def update(self, problem: Problem) -> None:
        self._problems[problem.problem_id] = problem


class InMemorySolutionRepository:
    def __init__(self) -> None:
        self._solutions: dict[UUID, Solution] = {}

    def add(self, solution: Solution) -> None:
        self._solutions[solution.solution_id] = solution

    def get(self, solution_id: UUID) -> Solution | None:
        return self._solutions.get(solution_id)

    def list_by_problem(self, problem_id: UUID) -> list[Solution]:
        results = [s for s in self._solutions.values() if s.problem_id == problem_id]
        results.sort(key=lambda s: s.confidence, reverse=True)
        return results

    def find_canonical_candidates(self, problem_id: UUID, similarity_threshold: float) -> list[Solution]:
        return [
            s
            for s in self._solutions.values()
            if s.problem_id == problem_id and s.canonical_id is None
        ]

    def update(self, solution: Solution) -> None:
        self._solutions[solution.solution_id] = solution


class InMemoryOutcomeRepository:
    def __init__(self) -> None:
        self._outcomes: list[Outcome] = []

    def add(self, outcome: Outcome) -> None:
        self._outcomes.append(outcome)

    def list_by_solution(self, solution_id: UUID) -> list[Outcome]:
        return [o for o in self._outcomes if o.solution_id == solution_id]

    def count_by_reporter(self, reporter_id: UUID, since: datetime) -> int:
        return sum(
            1
            for o in self._outcomes
            if o.reporter_id == reporter_id and o.created_at >= since
        )
