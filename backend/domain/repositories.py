from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from backend.domain.models import (
    Agent,
    Outcome,
    Problem,
    ProblemRelationship,
    ResearchCycle,
    Solution,
)


class AgentRepository(Protocol):
    def add(self, agent: Agent) -> None: ...

    def get(self, agent_id: UUID) -> Agent | None: ...

    def get_by_api_key_hash(self, api_key_hash: str) -> Agent | None: ...


class ProblemRepository(Protocol):
    def add(self, problem: Problem) -> None: ...

    def get(self, problem_id: UUID) -> Problem | None: ...

    def list_all(self) -> list[Problem]: ...

    def find_similar(
        self, embedding: list[float], threshold: float
    ) -> list[Problem]: ...

    def find_similar_scored(
        self, query_embedding: list[float]
    ) -> list[tuple[Problem, float]]: ...

    def find_hybrid(
        self,
        query_embedding: list[float] | None,
        query_text: str,
        limit: int,
    ) -> list[tuple[Problem, float]]: ...

    def find_by_error_signature(self, signature: str) -> Problem | None: ...

    def update(self, problem: Problem) -> None: ...

    def update_embedding_v2(
        self, problem_id: UUID, embedding: list[float] | None
    ) -> None:
        """Side-channel write of the v2 embedding column for dual-write
        during the EMBEDDING_VERSION cutover. Implementations may no-op when
        no v2 column exists (in-memory repo)."""
        ...

    def delete(self, problem_id: UUID) -> None: ...

    def find_unreviewed(
        self,
        limit: int,
        retry_error_before: datetime | None = None,
    ) -> list[Problem]: ...

    def find_research_candidates(
        self, limit: int = 10, offset: int = 0, max_confidence: float = 1.0
    ) -> list[Problem]: ...

    def list_being_researched(self, timeout_seconds: int = 360) -> list[Problem]:
        """Return Problems whose research_started_at is within the freshness window.

        A row is included iff research_started_at is non-null AND
        (utc_now() - research_started_at).total_seconds() < timeout_seconds.
        Order: research_started_at DESC.
        """
        ...


class SolutionRepository(Protocol):
    def add(self, solution: Solution) -> None: ...

    def get(self, solution_id: UUID) -> Solution | None: ...

    def list_by_problem(self, problem_id: UUID) -> list[Solution]: ...

    def update(self, solution: Solution) -> None: ...

    def delete(self, solution_id: UUID) -> None: ...

    def find_unreviewed(
        self,
        limit: int,
        retry_error_before: datetime | None = None,
    ) -> list[Solution]: ...

    def list_by_problem_ranked(self, problem_id: UUID) -> list[Solution]: ...

    def find_superseded(self, problem_id: UUID) -> list[Solution]: ...


class OutcomeRepository(Protocol):
    def add(self, outcome: Outcome) -> None: ...

    def list_by_solution(self, solution_id: UUID) -> list[Outcome]: ...

    def list_by_problem(
        self, problem_id: UUID, solution_ids: list[UUID]
    ) -> list[Outcome]: ...

    def count_by_reporter(self, reporter_id: UUID, since: datetime) -> int: ...

    def list_by_reporter(self, reporter_id: UUID) -> list[Outcome]: ...

    def aggregate_usage_metrics(self, now: datetime) -> dict:
        """Return flywheel-health aggregates over the outcomes table.

        Output is a flat dict with eight ints:

        * ``outcomes_total``, ``outcomes_last_7d``, ``outcomes_last_30d``
        * ``verified_total``, ``observed_total``
        * ``unique_reporters_total``, ``unique_reporters_7d``,
          ``unique_reporters_30d``

        ``now`` is the upper bound for the time windows; pass
        ``utc_now()`` from the service layer.
        """
        ...

    def outcome_counts_by_solution_ids(
        self, solution_ids: list[UUID]
    ) -> dict[UUID, int]:
        """Return ``{solution_id: outcome_count}`` for the given solutions.

        Empty input returns an empty dict. Solutions with zero outcomes
        are absent from the result rather than mapped to ``0`` — callers
        treat missing as zero.
        """
        ...


class ResearchCycleRepository(Protocol):
    def add(self, cycle: ResearchCycle) -> None: ...

    def list_by_problem(self, problem_id: UUID) -> list[ResearchCycle]: ...

    def count_by_researcher(self, researcher_id: UUID, since: datetime) -> int: ...

    def get_last_researched_at(self, problem_id: UUID) -> datetime | None: ...

    def count_consecutive_no_improvement(self, problem_id: UUID) -> int: ...

    def get_latest_cycle_at(self) -> datetime | None:
        """Return MAX(research_cycles.created_at) or None on empty table."""
        ...


class ProblemRelationshipRepository(Protocol):
    def add(self, rel: ProblemRelationship) -> None: ...

    def find_related(
        self,
        problem_id: UUID,
        relationship_types: list[str] | None = None,
        min_score: float = 0.0,
        limit: int = 10,
    ) -> list[ProblemRelationship]: ...

    def delete_by_source(self, source_problem_id: UUID) -> None: ...
