from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import math
from uuid import UUID

from app.application.errors import DuplicateVoteError
from app.domain.models import Agent, Comment, Thread, TokenTransaction, Vote


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

    def search_similar(self, query_embedding: list[float]) -> list[tuple[Thread, float]]:
        rows: list[tuple[Thread, float]] = []
        for thread in self._threads.values():
            if thread.embedding is None:
                continue
            similarity = _cosine_similarity(query_embedding, thread.embedding)
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
        self._by_thread[existing.thread_id] = [value for value in rows if value != comment_id]

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


def _cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    if not vector_a or not vector_b or len(vector_a) != len(vector_b):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vector_a, vector_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)
