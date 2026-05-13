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
from backend.domain.search import (
    SearchDiagnostics,  # noqa: TC001  (used in Protocol annotation)
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

    def find_hybrid_with_diagnostics(
        self,
        query_embedding: list[float] | None,
        query_text: str,
        limit: int,
    ) -> tuple[list[tuple[Problem, float]], SearchDiagnostics]:
        """Same as ``find_hybrid``, but also reports which legs ran.

        The application layer uses the carrier to derive a
        ``search_mode`` label on the response so calling agents can
        detect when retrieval silently degraded (e.g. pgvector
        unavailable, dense leg empty, fallback served the row).
        """
        ...

    def retrieval_status(self) -> tuple[str, bool]:
        """Report ``(backend, pgvector_available)`` without issuing a search.

        Used by the health endpoint so a Railway pgvector outage shows
        up in monitoring even before a search would have surfaced the
        degradation. Cheap by contract — implementations must not run
        the hybrid pipeline.
        """
        ...

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

    def list_solution_ids_by_problem_ids(
        self, problem_ids: list[UUID]
    ) -> dict[UUID, list[UUID]]:
        """Return ``{problem_id: [solution_id, ...]}`` for the given problems.

        Empty input returns an empty dict. Problems with zero solutions
        appear in the result with an empty list (callers can rely on key
        presence). Implementations should issue ONE batched query rather
        than N per-problem lookups — the dashboard aggregator depends on
        this to avoid N+1 over the corpus.
        """
        ...

    def list_by_problem_ids(
        self, problem_ids: list[UUID]
    ) -> dict[UUID, list[Solution]]:
        """Return ``{problem_id: [Solution, ...]}`` for the given problems.

        Heavier than ``list_solution_ids_by_problem_ids`` because it
        materialises full Solution objects — use it only when callers
        need fields beyond ``solution_id`` (confidence, outcome_count,
        review_status). Same single-query contract.
        """
        ...


class OutcomeRepository(Protocol):
    def add(self, outcome: Outcome) -> None: ...

    def upsert(self, outcome: Outcome) -> tuple[Outcome, bool]:
        """Insert or update an outcome by ``(solution_id, reporter_id)``.

        When a row for the same pair already exists, its mutable fields
        (``success``, ``kind``, ``weight``, ``environment``, ``notes``,
        ``time_saved_seconds``, ``error_after``, ``created_at``) are
        replaced with the incoming outcome's values. The original
        ``outcome_id`` is retained so external references stay stable.

        Returns ``(persisted, inserted)`` where ``inserted`` is True
        when a new row was created and False when an existing row was
        updated — callers use the flag to know whether to bump
        outcome-counter aggregates.
        """
        ...

    def list_by_solution(self, solution_id: UUID) -> list[Outcome]: ...

    def list_by_problem(
        self, problem_id: UUID, solution_ids: list[UUID]
    ) -> list[Outcome]: ...

    def count_by_reporter(self, reporter_id: UUID, since: datetime) -> int: ...

    def oldest_created_at_by_reporter(
        self, reporter_id: UUID, since: datetime
    ) -> datetime | None:
        """Return the earliest ``created_at`` for outcomes from ``reporter_id``
        whose timestamp is on or after ``since``. Used by the rate-limit
        path to compute ``Retry-After`` without materialising the full
        reporter history.
        """
        ...

    def list_by_reporter(self, reporter_id: UUID) -> list[Outcome]: ...

    def list_by_solution_ids(self, solution_ids: list[UUID]) -> list[Outcome]:
        """Return all outcomes whose ``solution_id`` is in ``solution_ids``.

        Empty input returns an empty list. Order is unspecified. Single
        batched query — used by ``get_radar`` / ``get_metrics`` to avoid
        an N-per-solution outcome lookup. Callers bucket the result by
        ``solution_id`` themselves.
        """
        ...

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
