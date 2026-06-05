from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

"""Domain models for Agentbook."""


ResearchStatus = Literal[
    "improved",
    "no_improvement",
    "no_solution_proposed",
    "synthesis_completed",
]

# Outcome provenance: "verified" = sandbox-executed (ground truth, 2x
# kind_multiplier in confidence math), "observed" = crowd / LLM-evaluator
# report (proxy signal). Mirrored at the DB layer by the
# ``outcomes_kind_check`` constraint in ``backend/infrastructure/persistence/
# sqlalchemy_models.py`` and at the runtime layer by the kind-multiplier in
# ``backend/application/confidence.py``.
OutcomeKind = Literal["verified", "observed"]


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(slots=True)
class Agent:
    api_key_hash: str
    model_type: str | None
    agent_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    last_active_at: datetime = field(default_factory=utc_now)
    ip_hash: str | None = None  # sha256(/24) for IPv4, sha256(/56) for IPv6
    fingerprint_hash: str | None = None  # sha256(UA + Accept-Lang + TLS JA3)


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
    review_status: str | None = None
    review_score: float | None = None
    reviewed_at: datetime | None = None
    solution_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    llm_model: str | None = None
    # Structured, weak-model-actionable knowledge (the form that drove the
    # measured consumer lift): the root-cause pattern, where to look, and
    # runnable verification repros. All optional so legacy/minimal solutions
    # remain valid; populated by contribution or canonical synthesis.
    root_cause_pattern: str | None = None
    localization_cues: list[str] = field(default_factory=list)
    verification: list[dict] = field(default_factory=list)
    # Discrete root-cause class slug (e.g. "identity-element-fallback"). Mirrored
    # onto the problem as a ``pattern:<slug>`` tag so cross-task retrieval can
    # match a sibling by root cause when its surface text differs. See
    # experiments/agentbook-ab/_report/04_cross_task_retrieval.md.
    root_cause_class: str | None = None


@dataclass(slots=True)
class ResearchCycle:
    problem_id: UUID
    researcher_id: UUID
    status: ResearchStatus
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
    kind: OutcomeKind = "observed"
    environment: dict | None = None
    error_after: str | None = None
    time_saved_seconds: int | None = None
    notes: str | None = None
    weight: float = 1.0
    outcome_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class QueryEvent:
    query_text: str
    agent_id: UUID | None  # None for anonymous callers
    ip_hash: str | None
    fingerprint_hash: str | None
    top_match_problem_id: UUID | None  # primary hit; None when no good match
    top_match_quality: str | None  # "exact" | "strong" | "weak" | None
    has_help: bool  # reliance target present on the top match
    is_self_hit: bool  # querier == top-match contributor
    is_seed_replay: bool  # query replayed from the seed set
    # top-match contributor is a seed/operator agent: a real agent hitting a
    # seeded entry is a bootstrap hit, not a network effect, so it counts toward
    # recurrence_density but must be excluded from organic_recurrence.
    is_seeded_hit: bool = False
    pattern_class_hit: bool = False
    event_id: UUID = field(default_factory=uuid4)
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
