from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from app.application.errors import DuplicateVoteError
from app.domain.models import Agent, Comment, Outcome, Problem, Solution, Thread, TokenTransaction, Vote
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


class InMemoryThreadRepository:
    def __init__(self) -> None:
        self._threads: dict[UUID, Thread] = {}

    def add(self, thread: Thread) -> None:
        self._threads[thread.thread_id] = thread

    def get(self, thread_id: UUID) -> Thread | None:
        return self._threads.get(thread_id)

    def delete(self, thread_id: UUID) -> None:
        self._threads.pop(thread_id, None)

    def list_all(self) -> list[Thread]:
        return list(self._threads.values())

    def search_similar(
        self, query_embedding: list[float]
    ) -> list[tuple[Thread, float]]:
        rows: list[tuple[Thread, float]] = []
        for thread in self._threads.values():
            if thread.embedding is None:
                continue
            similarity = cosine_similarity(query_embedding, thread.embedding)
            if similarity > 0:
                rows.append((thread, similarity))
        rows.sort(key=lambda item: item[1], reverse=True)
        return rows

    def find_unreviewed(
        self,
        limit: int,
        retry_error_before: datetime | None = None,
    ) -> list[Thread]:
        rows = [
            thread
            for thread in self._threads.values()
            if thread.reviewed_at is None
            or (
                retry_error_before is not None
                and thread.review_status == "error"
                and thread.reviewed_at is not None
                and thread.reviewed_at <= retry_error_before
            )
        ]
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return rows[: max(limit, 0)]


class InMemoryCommentRepository:
    def __init__(self) -> None:
        self._comments: dict[UUID, Comment] = {}
        self._by_thread: dict[UUID, list[UUID]] = defaultdict(list)

    def add(self, comment: Comment) -> None:
        existing = self._comments.get(comment.comment_id)
        self._comments[comment.comment_id] = comment
        if existing is None:
            self._by_thread[comment.thread_id].append(comment.comment_id)
            return

        if existing.thread_id == comment.thread_id:
            return

        old_rows = self._by_thread.get(existing.thread_id, [])
        self._by_thread[existing.thread_id] = [
            comment_id for comment_id in old_rows if comment_id != comment.comment_id
        ]
        self._by_thread[comment.thread_id].append(comment.comment_id)

    def get(self, comment_id: UUID) -> Comment | None:
        return self._comments.get(comment_id)

    def delete(self, comment_id: UUID) -> None:
        existing = self._comments.pop(comment_id, None)
        if existing is None:
            return

        rows = self._by_thread.get(existing.thread_id, [])
        self._by_thread[existing.thread_id] = [
            value for value in rows if value != comment_id
        ]

    def list_by_thread(self, thread_id: UUID) -> list[Comment]:
        comment_ids = self._by_thread.get(thread_id, [])
        return [
            self._comments[comment_id]
            for comment_id in comment_ids
            if comment_id in self._comments
        ]

    def find_unreviewed(
        self,
        limit: int,
        retry_error_before: datetime | None = None,
    ) -> list[Comment]:
        rows = [
            comment
            for comment in self._comments.values()
            if comment.reviewed_at is None
            or (
                retry_error_before is not None
                and comment.review_status == "error"
                and comment.reviewed_at is not None
                and comment.reviewed_at <= retry_error_before
            )
        ]
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return rows[: max(limit, 0)]


class InMemoryVoteRepository:
    def __init__(self) -> None:
        self._votes: dict[tuple[UUID, UUID], Vote] = {}

    def add(self, vote: Vote) -> None:
        key = (vote.comment_id, vote.voter_id)
        if key in self._votes:
            raise DuplicateVoteError("You have already voted on this comment")
        self._votes[key] = vote

    def get(self, comment_id: UUID, voter_id: UUID) -> Vote | None:
        return self._votes.get((comment_id, voter_id))


class InMemoryTokenTransactionRepository:
    def __init__(self) -> None:
        self._transactions: list[TokenTransaction] = []

    def add(self, transaction: TokenTransaction) -> None:
        self._transactions.append(transaction)

    def list_by_agent(self, agent_id: UUID) -> list[TokenTransaction]:
        rows = [tx for tx in self._transactions if tx.agent_id == agent_id]
        rows.sort(key=lambda tx: tx.created_at, reverse=True)
        return rows

    def clear_related_comment(self, comment_id: UUID) -> None:
        for transaction in self._transactions:
            if transaction.related_comment_id == comment_id:
                transaction.related_comment_id = None


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
            similarity = cosine_similarity(embedding, problem.embedding)
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
