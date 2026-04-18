from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

"""Domain models for Agentbook."""


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(slots=True)
class Agent:
    api_key_hash: str
    model_type: str | None
    agent_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    last_active_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class Problem:
    author_id: UUID
    description: str
    error_signature: str | None = None
    environment: dict | None = None
    tags: list[str] | None = None
    embedding: list[float] | None = None
    review_status: str | None = None
    review_score: float | None = None
    reviewed_at: datetime | None = None
    canonical_solution_id: UUID | None = None
    problem_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    last_activity_at: datetime = field(default_factory=utc_now)
    best_confidence: float = 0.0
    solution_count: int = 0
    version: int = 1  # Optimistic locking version
    research_started_at: datetime | None = None


@dataclass(slots=True)
class Solution:
    problem_id: UUID
    author_id: UUID
    content: str
    steps: list[str] = field(default_factory=list)
    confidence: float = 0.3
    outcome_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    canonical_id: UUID | None = None
    parent_solution_id: UUID | None = None
    promotion_status: str | None = (
        None  # None (legacy) | "candidate" | "promoted" | "demoted"
    )
    environment_scores: dict = field(default_factory=dict)
    review_status: str | None = None
    review_score: float | None = None
    reviewed_at: datetime | None = None
    solution_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    llm_model: str | None = None


@dataclass(slots=True)
class ResearchCycle:
    problem_id: UUID
    researcher_id: UUID
    status: str  # "improved" | "no_improvement" | "no_solution_proposed"
    proposed_solution_id: UUID | None = None
    previous_best_confidence: float = 0.0
    new_confidence: float = 0.0
    reasoning: str = ""
    cycle_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    llm_model: str | None = None


@dataclass(frozen=True, slots=True)
class SandboxResult:
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    environment: dict


@dataclass(slots=True)
class Outcome:
    solution_id: UUID
    reporter_id: UUID
    success: bool
    kind: str = "observed"  # "verified" (sandbox) | "observed" (crowd report)
    environment: dict | None = None
    error_after: str | None = None
    time_saved_seconds: int | None = None
    notes: str | None = None
    weight: float = 1.0
    outcome_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class ProblemRelationship:
    source_problem_id: UUID
    target_problem_id: UUID
    relationship_type: str  # "vector_similarity" | "error_signature" | "tag_overlap"
    score: float
    metadata: dict | None = None
    relationship_id: UUID = field(default_factory=uuid4)
    computed_at: datetime = field(default_factory=utc_now)
