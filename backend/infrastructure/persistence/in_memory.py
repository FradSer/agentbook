from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from backend.application._recurrence import (
    compute_recurrence_rollup,
    same_query_identity,
)
from backend.application.service import RESEARCH_TIMEOUT_SECONDS
from backend.domain.models import (
    Agent,
    Outcome,
    Problem,
    ProblemRelationship,
    QueryEvent,
    ResearchCycle,
    Solution,
)
from backend.domain.search import SearchDiagnostics
from backend.infrastructure.persistence.vector_utils import cosine_similarity

if TYPE_CHECKING:
    from backend.domain.repositories import AgentRepository


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


class InMemoryProblemRepository:
    def __init__(self) -> None:
        self._problems: dict[UUID, Problem] = {}

    def add(self, problem: Problem) -> None:
        self._problems[problem.problem_id] = problem

    def get(self, problem_id: UUID) -> Problem | None:
        return self._problems.get(problem_id)

    def get_by_ids(self, problem_ids: list[UUID]) -> dict[UUID, Problem]:
        return {
            pid: self._problems[pid] for pid in problem_ids if pid in self._problems
        }

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

    def find_similar_scored(
        self, query_embedding: list[float]
    ) -> list[tuple[Problem, float]]:
        rows: list[tuple[Problem, float]] = []
        for problem in self._problems.values():
            if problem.embedding is None:
                continue
            if problem.review_status != "approved":
                continue
            similarity = cosine_similarity(query_embedding, problem.embedding)
            if similarity > 0:
                rows.append((problem, similarity))
        rows.sort(key=lambda item: item[1], reverse=True)
        return rows

    def find_hybrid(
        self,
        query_embedding: list[float] | None,
        query_text: str,
        limit: int,
    ) -> list[tuple[Problem, float]]:
        results, _ = self.find_hybrid_with_diagnostics(
            query_embedding=query_embedding,
            query_text=query_text,
            limit=limit,
        )
        return results

    def retrieval_status(self) -> tuple[str, bool]:
        return ("memory", False)

    def find_hybrid_with_diagnostics(
        self,
        query_embedding: list[float] | None,
        query_text: str,
        limit: int,
    ) -> tuple[list[tuple[Problem, float]], SearchDiagnostics]:
        from backend.domain.search import rrf_fuse

        approved = [p for p in self._problems.values() if p.review_status == "approved"]

        dense: list[Problem] = []
        if query_embedding is not None:
            with_scores = [
                (p, cosine_similarity(query_embedding, p.embedding))
                for p in approved
                if p.embedding is not None
            ]
            with_scores.sort(key=lambda item: item[1], reverse=True)
            dense = [p for p, score in with_scores if score > 0]

        sparse: list[Problem] = []
        if query_text:
            terms = {t for t in query_text.lower().split() if t}
            with_overlap = []
            for p in approved:
                searchable = " ".join(
                    part
                    for part in (
                        p.description,
                        p.error_signature or "",
                        " ".join(p.tags or []),
                    )
                    if part
                )
                tokens = set(searchable.lower().split())
                overlap = len(terms & tokens)
                if overlap > 0:
                    with_overlap.append((p, overlap))
            with_overlap.sort(key=lambda item: item[1], reverse=True)
            sparse = [p for p, _ in with_overlap]

        diagnostics = SearchDiagnostics(
            backend="memory",
            pgvector_available=False,
            dense_hits=len(dense),
            sparse_hits=len(sparse),
        )
        if not dense and not sparse:
            return [], diagnostics
        return rrf_fuse([dense, sparse], k=60, limit=limit), diagnostics

    def find_by_error_signature(self, signature: str) -> Problem | None:
        for problem in self._problems.values():
            if problem.error_signature == signature:
                return problem
        return None

    def update(self, problem: Problem) -> None:
        self._problems[problem.problem_id] = problem

    def update_embedding_v2(
        self, problem_id: UUID, embedding: list[float] | None
    ) -> None:
        # In-memory mode has no separate v2 column; the dual-write is a no-op
        # because there is no SQL schema to bifurcate. Tests and DEMO_MODE
        # rely on this behaviour.
        del problem_id, embedding

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

    def find_research_candidates(
        self,
        limit: int = 10,
        offset: int = 0,
        max_confidence: float = 1.0,
        min_solution_count: int = 0,
    ) -> list[Problem]:
        approved = [
            p
            for p in self._problems.values()
            if p.review_status == "approved"
            and p.best_confidence < max_confidence
            and p.solution_count >= min_solution_count
        ]
        approved.sort(key=lambda p: (p.solution_count, p.best_confidence))
        return approved[offset : offset + limit]

    def list_being_researched(
        self, timeout_seconds: int = RESEARCH_TIMEOUT_SECONDS
    ) -> list[Problem]:
        now = datetime.now(tz=UTC)
        fresh = [
            p
            for p in self._problems.values()
            if p.research_started_at is not None
            and (now - p.research_started_at).total_seconds() < timeout_seconds
        ]
        fresh.sort(key=lambda p: p.research_started_at, reverse=True)
        return fresh


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
        results = [s for s in self._solutions.values() if s.problem_id == problem_id]
        results.sort(key=lambda s: (s.canonical_id is None, s.confidence), reverse=True)
        return results

    def _bucket_solutions_by_problem(
        self, problem_ids: list[UUID], project
    ) -> dict[UUID, list]:
        if not problem_ids:
            return {}
        target = set(problem_ids)
        out: dict[UUID, list] = {pid: [] for pid in target}
        for s in self._solutions.values():
            if s.problem_id in target:
                out[s.problem_id].append(project(s))
        return out

    def list_solution_ids_by_problem_ids(
        self, problem_ids: list[UUID]
    ) -> dict[UUID, list[UUID]]:
        return self._bucket_solutions_by_problem(problem_ids, lambda s: s.solution_id)

    def list_by_problem_ids(
        self, problem_ids: list[UUID]
    ) -> dict[UUID, list[Solution]]:
        return self._bucket_solutions_by_problem(problem_ids, lambda s: s)

    def find_superseded(self, problem_id: UUID) -> list[Solution]:
        return [
            s
            for s in self._solutions.values()
            if s.problem_id == problem_id and s.canonical_id is not None
        ]


class InMemoryOutcomeRepository:
    def __init__(self) -> None:
        self._outcomes: list[Outcome] = []

    def add(self, outcome: Outcome) -> None:
        self._outcomes.append(outcome)

    def upsert(self, outcome: Outcome) -> tuple[Outcome, bool]:
        for idx, existing in enumerate(self._outcomes):
            if (
                existing.solution_id == outcome.solution_id
                and existing.reporter_id == outcome.reporter_id
            ):
                # Preserve the original outcome_id — external references
                # (logs, tickets, lineage) point at it. Only replace the
                # mutable signal fields.
                merged = Outcome(
                    outcome_id=existing.outcome_id,
                    solution_id=outcome.solution_id,
                    reporter_id=outcome.reporter_id,
                    success=outcome.success,
                    kind=outcome.kind,
                    weight=outcome.weight,
                    environment=outcome.environment,
                    notes=outcome.notes,
                    time_saved_seconds=outcome.time_saved_seconds,
                    error_after=outcome.error_after,
                    created_at=outcome.created_at,
                )
                self._outcomes[idx] = merged
                return merged, False
        self._outcomes.append(outcome)
        return outcome, True

    def list_by_solution(self, solution_id: UUID) -> list[Outcome]:
        return [o for o in self._outcomes if o.solution_id == solution_id]

    def list_by_problem(
        self, problem_id: UUID, solution_ids: list[UUID]
    ) -> list[Outcome]:
        id_set = set(solution_ids)
        return [o for o in self._outcomes if o.solution_id in id_set]

    def count_by_reporter(self, reporter_id: UUID, since: datetime) -> int:
        return sum(
            1
            for o in self._outcomes
            if o.reporter_id == reporter_id and o.created_at >= since
        )

    def oldest_created_at_by_reporter(
        self, reporter_id: UUID, since: datetime
    ) -> datetime | None:
        in_window = (
            o.created_at
            for o in self._outcomes
            if o.reporter_id == reporter_id and o.created_at >= since
        )
        return min(in_window, default=None)

    def list_by_reporter(self, reporter_id: UUID) -> list[Outcome]:
        return [o for o in self._outcomes if o.reporter_id == reporter_id]

    def aggregate_usage_metrics(self, now: datetime) -> dict:
        seven_ago = now - timedelta(days=7)
        thirty_ago = now - timedelta(days=30)

        last_7d = 0
        last_30d = 0
        verified = 0
        observed = 0
        reporters_total: set[UUID] = set()
        reporters_7d: set[UUID] = set()
        reporters_30d: set[UUID] = set()

        for o in self._outcomes:
            reporters_total.add(o.reporter_id)
            if o.created_at >= seven_ago:
                last_7d += 1
                reporters_7d.add(o.reporter_id)
            if o.created_at >= thirty_ago:
                last_30d += 1
                reporters_30d.add(o.reporter_id)
            if o.kind == "verified":
                verified += 1
            elif o.kind == "observed":
                observed += 1

        return {
            "outcomes_total": len(self._outcomes),
            "outcomes_last_7d": last_7d,
            "outcomes_last_30d": last_30d,
            "verified_total": verified,
            "observed_total": observed,
            "unique_reporters_total": len(reporters_total),
            "unique_reporters_7d": len(reporters_7d),
            "unique_reporters_30d": len(reporters_30d),
        }

    def outcome_counts_by_solution_ids(
        self, solution_ids: list[UUID]
    ) -> dict[UUID, int]:
        if not solution_ids:
            return {}
        target = set(solution_ids)
        counts: dict[UUID, int] = {}
        for o in self._outcomes:
            if o.solution_id in target:
                counts[o.solution_id] = counts.get(o.solution_id, 0) + 1
        return counts

    def list_by_solution_ids(self, solution_ids: list[UUID]) -> list[Outcome]:
        if not solution_ids:
            return []
        target = set(solution_ids)
        return [o for o in self._outcomes if o.solution_id in target]


class InMemoryQueryEventRepository:
    def __init__(self) -> None:
        self._events: list[QueryEvent] = []

    def add(self, event: QueryEvent) -> None:
        self._events.append(event)

    def add_with_dedup(
        self,
        event: QueryEvent,
        agents: AgentRepository,
        *,
        exclude_seed_replay: bool = True,
        exclude_self_hits: bool = True,
        dedup_window_seconds: int = 600,
    ) -> bool:
        if exclude_seed_replay and event.is_seed_replay:
            return False
        if exclude_self_hits and event.is_self_hit:
            return False

        window = timedelta(seconds=dedup_window_seconds)
        for existing in self._events:
            if existing.top_match_problem_id != event.top_match_problem_id:
                continue
            if abs(existing.created_at - event.created_at) > window:
                continue
            if same_query_identity(existing, event, agents):
                return False

        self._events.append(event)
        return True

    def list_all(self, since: datetime | None = None) -> list[QueryEvent]:
        if since is None:
            return list(self._events)
        return [e for e in self._events if e.created_at >= since]

    def query_count_for_problem(
        self, problem_id: UUID, since: datetime | None = None
    ) -> int:
        return sum(
            1
            for e in self._events
            if e.top_match_problem_id == problem_id
            and not e.is_seed_replay
            and not e.is_self_hit
            and (since is None or e.created_at >= since)
        )

    def recurrence_rollup(
        self,
        *,
        seed_agent_ids: frozenset[UUID] = frozenset(),
        since: datetime | None = None,
    ) -> dict:
        return compute_recurrence_rollup(
            self.list_all(since=since), seed_agent_ids=seed_agent_ids
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

    def get_last_researched_at(self, problem_id: UUID) -> datetime | None:
        cycles = [c for c in self._cycles if c.problem_id == problem_id]
        if not cycles:
            return None
        return max(c.created_at for c in cycles)

    def get_latest_cycle_at(self) -> datetime | None:
        if not self._cycles:
            return None
        return max(c.created_at for c in self._cycles)

    def list_recent(self, limit: int) -> list[ResearchCycle]:
        ordered = sorted(self._cycles, key=lambda c: c.created_at, reverse=True)
        return ordered[:limit]

    def count_since(self, since: datetime) -> int:
        return sum(1 for c in self._cycles if c.created_at >= since)

    def count_consecutive_no_improvement(self, problem_id: UUID) -> int:
        cycles = sorted(
            [c for c in self._cycles if c.problem_id == problem_id],
            key=lambda c: c.created_at,
            reverse=True,
        )
        count = 0
        for cycle in cycles:
            if cycle.status in ("no_improvement", "no_solution_proposed"):
                count += 1
            else:
                break
        return count


class InMemoryProblemRelationshipRepository:
    def __init__(self) -> None:
        self._rels: list[ProblemRelationship] = []

    def add(self, rel: ProblemRelationship) -> None:
        self._rels.append(rel)

    def find_related(
        self,
        problem_id: UUID,
        relationship_types: list[str] | None = None,
        min_score: float = 0.0,
        limit: int = 10,
    ) -> list[ProblemRelationship]:
        results = [
            r
            for r in self._rels
            if r.source_problem_id == problem_id
            and r.score >= min_score
            and (
                relationship_types is None or r.relationship_type in relationship_types
            )
        ]
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def delete_by_source(self, source_problem_id: UUID) -> None:
        self._rels = [r for r in self._rels if r.source_problem_id != source_problem_id]
