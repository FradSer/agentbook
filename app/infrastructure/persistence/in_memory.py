from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from app.domain.models import Agent, Outcome, Problem, ResearchCycle, Solution, TokenTransaction
from app.infrastructure.persistence.vector_utils import cosine_similarity


class InMemoryAgentRepository:
    def __init__(self) -> None:
        self._agents: dict[UUID, Agent] = {}
        self._by_hash: dict[str, UUID] = {}

    def add(self, agent: Agent) -> None:
        self._agents[agent.agent_id] = agent
        self._by_hash[agent.api_key_hash] = agent.agent_id

    def get(self, agent_id: UUID) -> Agent | None:
        return self._agents.get(agent_id)

    def get_by_api_key_hash(self, api_key_hash: str) -> Agent | None:
        agent_id = self._by_hash.get(api_key_hash)
        if agent_id is None:
            return None
        return self._agents.get(agent_id)


class InMemoryTokenTransactionRepository:
    def __init__(self) -> None:
        self._transactions: list[TokenTransaction] = []

    def add(self, transaction: TokenTransaction) -> None:
        self._transactions.append(transaction)

    def list_by_agent(self, agent_id: UUID) -> list[TokenTransaction]:
        rows = [tx for tx in self._transactions if tx.agent_id == agent_id]
        rows.sort(key=lambda tx: tx.created_at, reverse=True)
        return rows

    def clear_related_solution(self, solution_id: UUID) -> None:
        for transaction in self._transactions:
            if transaction.related_solution_id == solution_id:
                transaction.related_solution_id = None


class InMemoryProblemRepository:
    def __init__(self) -> None:
        self._problems: dict[UUID, Problem] = {}

    def add(self, problem: Problem) -> None:
        self._problems[problem.problem_id] = problem

    def get(self, problem_id: UUID) -> Problem | None:
        return self._problems.get(problem_id)

    def delete(self, problem_id: UUID) -> None:
        self._problems.pop(problem_id, None)

    def list_all(self) -> list[Problem]:
        return list(self._problems.values())

    def find_similar(self, embedding: list[float], threshold: float) -> list[Problem]:
        results: list[Problem] = []
        for problem in self._problems.values():
            if problem.embedding is None:
                continue
            similarity = cosine_similarity(embedding, problem.embedding)
            if similarity >= threshold:
                results.append(problem)
        return results

    def search_similar(self, query_embedding: list[float]) -> list[tuple[Problem, float]]:
        rows: list[tuple[Problem, float]] = []
        for problem in self._problems.values():
            if problem.embedding is None:
                continue
            similarity = cosine_similarity(query_embedding, problem.embedding)
            if similarity > 0:
                rows.append((problem, similarity))
        rows.sort(key=lambda item: item[1], reverse=True)
        return rows

    def find_by_error_signature(self, signature: str) -> Problem | None:
        for problem in self._problems.values():
            if problem.error_signature == signature:
                return problem
        return None

    def update(self, problem: Problem) -> None:
        self._problems[problem.problem_id] = problem

    def find_unreviewed(
        self,
        limit: int,
        retry_error_before: datetime | None = None,
    ) -> list[Problem]:
        rows = [
            problem
            for problem in self._problems.values()
            if problem.review_status is None
            or (
                retry_error_before is not None
                and problem.review_status == "error"
                and (
                    problem.reviewed_at is None
                    or problem.reviewed_at <= retry_error_before
                )
            )
        ]
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return rows[: max(limit, 0)]

    def find_research_candidates(self, limit: int = 10, offset: int = 0) -> list[Problem]:
        approved = [p for p in self._problems.values() if p.review_status == "approved"]
        approved.sort(key=lambda p: p.best_confidence)
        return approved[offset : offset + limit]


class InMemorySolutionRepository:
    def __init__(self) -> None:
        self._solutions: dict[UUID, Solution] = {}

    def add(self, solution: Solution) -> None:
        self._solutions[solution.solution_id] = solution

    def get(self, solution_id: UUID) -> Solution | None:
        return self._solutions.get(solution_id)

    def delete(self, solution_id: UUID) -> None:
        self._solutions.pop(solution_id, None)

    def list_by_problem(self, problem_id: UUID) -> list[Solution]:
        results = [s for s in self._solutions.values() if s.problem_id == problem_id]
        results.sort(key=lambda s: s.confidence, reverse=True)
        return results

    def update(self, solution: Solution) -> None:
        self._solutions[solution.solution_id] = solution

    def find_unreviewed(
        self,
        limit: int,
        retry_error_before: datetime | None = None,
    ) -> list[Solution]:
        rows = [
            solution
            for solution in self._solutions.values()
            if solution.review_status is None
            or (
                retry_error_before is not None
                and solution.review_status == "error"
                and (
                    solution.reviewed_at is None
                    or solution.reviewed_at <= retry_error_before
                )
            )
        ]
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return rows[: max(limit, 0)]

    def list_by_problem_ranked(self, problem_id: UUID) -> list[Solution]:
        results = [
            s
            for s in self._solutions.values()
            if s.problem_id == problem_id and s.review_status == "approved"
        ]
        results.sort(key=lambda s: s.confidence, reverse=True)
        return results

    def find_superseded(self, problem_id: UUID) -> list[Solution]:
        return [
            s for s in self._solutions.values()
            if s.problem_id == problem_id and s.canonical_id is not None
        ]


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


class InMemoryResearchCycleRepository:
    def __init__(self) -> None:
        self._cycles: list[ResearchCycle] = []

    def add(self, cycle: ResearchCycle) -> None:
        self._cycles.append(cycle)

    def list_by_problem(self, problem_id: UUID) -> list[ResearchCycle]:
        results = [c for c in self._cycles if c.problem_id == problem_id]
        results.sort(key=lambda c: c.created_at, reverse=True)
        return results

    def count_by_researcher(self, researcher_id: UUID, since: datetime) -> int:
        return sum(
            1
            for c in self._cycles
            if c.researcher_id == researcher_id and c.created_at >= since
        )

    def last_researched_at(self, problem_id: UUID) -> datetime | None:
        cycles = [c for c in self._cycles if c.problem_id == problem_id]
        if not cycles:
            return None
        return max(c.created_at for c in cycles)
