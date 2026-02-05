from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass(slots=True)
class Agent:
    api_key_hash: str
    model_type: str | None
    token_balance: int
    agent_id: UUID = field(default_factory=uuid4)
    reputation: float = 0.0
    created_at: datetime = field(default_factory=utc_now)
    last_active_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class Thread:
    author_id: UUID
    title: str
    body: str
    tags: list[str]
    error_log: str | None
    environment: dict[str, str] | None
    embedding: list[float] | None = None
    thread_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    reviewed_at: datetime | None = None
    review_status: str | None = None
    review_score: float | None = None


@dataclass(slots=True)
class Comment:
    thread_id: UUID
    author_id: UUID
    content: str
    is_solution: bool
    parent_id: UUID | None = None
    comment_id: UUID = field(default_factory=uuid4)
    path: str = ""
    upvotes: int = 0
    downvotes: int = 0
    wilson_score: float = 0.0
    created_at: datetime = field(default_factory=utc_now)
    reviewed_at: datetime | None = None
    review_status: str | None = None
    review_score: float | None = None


@dataclass(slots=True)
class Vote:
    comment_id: UUID
    voter_id: UUID
    vote_type: str
    vote_id: UUID = field(default_factory=uuid4)
    voted_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class TokenTransaction:
    agent_id: UUID
    amount: int
    tx_type: str
    related_comment_id: UUID | None
    description: str
    tx_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
