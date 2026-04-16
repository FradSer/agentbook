from __future__ import annotations

import json
import logging
import random
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from backend.domain.repositories import ProblemRelationshipRepository

from backend.application.confidence import (
    calculate_confidence,
    calculate_environment_scores,
    evaluate_improvement,
    is_content_regression,
    normalize_environment,
)
from backend.application.errors import (
    ConcurrentModificationError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
)
from backend.application.gate import check_spam
from backend.core.config import settings
from backend.core.search_cache import TTLCache
from backend.domain.models import (
    Agent,
    Outcome,
    Problem,
    ProblemRelationship,
    ResearchCycle,
    Solution,
    utc_now,
)
from backend.domain.repositories import (
    AgentRepository,
    OutcomeRepository,
    ProblemRepository,
    ResearchCycleRepository,
    SolutionRepository,
)
from backend.domain.services import (
    EmbeddingProvider,
    EvaluatorProvider,
    SandboxProvider,
)
from backend.infrastructure.security import generate_api_key, hash_api_key

logger = logging.getLogger(__name__)

_SEARCH_CACHE_MAXSIZE = 256
_SEARCH_CACHE_TTL_SECONDS = 300.0

# Spam protection; unrelated to the removed token economy.
_RATE_LIMIT = 10
_RATE_WINDOW_HOURS = 1

# Dedicated UUID for the LLM evaluator agent so synthetic outcomes count
# as "external" in the Bayesian reporter-diversity penalty.
EVALUATOR_AGENT_ID = UUID("00000000-0000-0000-0000-000000000002")
SANDBOX_AGENT_ID = UUID("00000000-0000-0000-0000-000000000003")


class AgentbookService:
    def __init__(
        self,
        agents: AgentRepository,
        embedding_provider: EmbeddingProvider | None = None,
        evaluator: EvaluatorProvider | None = None,
        sandbox: SandboxProvider | None = None,
        problems: ProblemRepository = None,
        solutions: SolutionRepository = None,
        outcomes: OutcomeRepository = None,
        research_cycles: ResearchCycleRepository = None,
        problem_relationships: ProblemRelationshipRepository | None = None,
    ) -> None:
        self._agents = agents
        self._embedding_provider = embedding_provider
        self._evaluator = evaluator
        self._sandbox = sandbox
        self._problems = problems
        self._solutions = solutions
        self._outcomes = outcomes
        self._research_cycles = research_cycles
        self._problem_relationships = problem_relationships
        self._synthetic_agents_ensured: set[UUID] = set()
        self._search_cache = TTLCache(
            maxsize=_SEARCH_CACHE_MAXSIZE, ttl=_SEARCH_CACHE_TTL_SECONDS
        )

    def register_agent(self, model_type: str | None) -> tuple[Agent, str]:
        api_key = generate_api_key()
        agent = Agent(
            api_key_hash=hash_api_key(api_key),
            model_type=model_type,
        )
        self._agents.add(agent)
        return agent, api_key

    def authenticate(self, api_key: str, agent_info: str | None = None) -> Agent:
        agent = self._agents.get_by_api_key_hash(hash_api_key(api_key))
        if agent is None:
            raise UnauthorizedError("Invalid API Key")

        agent.last_active_at = utc_now()
        parsed_model = self._extract_model_from_agent_info(agent_info)
        if parsed_model is not None:
            agent.model_type = parsed_model

        self._agents.add(agent)
        return agent

    def create_problem(
        self,
        author_id: UUID,
        description: str,
        error_signature: str | None = None,
        environment: dict | None = None,
        tags: list[str] | None = None,
    ) -> Problem:
        self._ensure_agent_exists(author_id)
        gate = check_spam(description, "problem")
        if not gate.passed:
            raise ValueError(gate.reason)
        problem = Problem(
            author_id=author_id,
            description=description,
            error_signature=error_signature,
            environment=environment,
            tags=tags,
            review_status="approved",
        )
        self._problems.add(problem)
        return problem

    def create_solution(
        self,
        problem_id: UUID,
        author_id: UUID,
        content: str,
        steps: list[str] | None = None,
        parent_solution_id: UUID | None = None,
        llm_model: str | None = None,
    ) -> Solution:
        self._ensure_agent_exists(author_id)
        problem = self._problems.get(problem_id)
        if problem is None:
            raise NotFoundError("Problem not found")
        gate = check_spam(content, "solution", {"steps": steps} if steps else None)
        if not gate.passed:
            raise ValueError(gate.reason)
        solution = Solution(
            problem_id=problem_id,
            author_id=author_id,
            content=content,
            steps=steps or [],
            parent_solution_id=parent_solution_id,
            review_status="approved",
            llm_model=self._llm_model_for_author(author_id, llm_model),
        )
        self._solutions.add(solution)
        problem.solution_count += 1
        problem.last_activity_at = utc_now()
        self._problems.update(problem)
        return solution

    async def generate_problem_embedding(self, problem_id: UUID) -> None:
        if self._embedding_provider is None:
            return
        problem = self._problems.get(problem_id)
        if problem is None:
            return
        embedding = await self._embedding_provider.embed(problem.description)
        problem.embedding = embedding
        self._problems.update(problem)

        if settings.knowledge_graph_enabled and self._problem_relationships is not None:
            self._compute_relationships(problem)

    def search_problems(
        self,
        query: str,
        limit: int,
        error_log: str | None = None,
        include: set[str] | None = None,
        format: str = "concise",
        environment: dict | None = None,
    ) -> dict:

        env_key = normalize_environment(environment) if environment else None
        cache_key = (
            query,
            error_log,
            limit,
            tuple(sorted(include)) if include else None,
            format,
            env_key,
        )
        cached = self._search_cache.get(cache_key)
        if cached is not None:
            return cached
        rows = self._search_problems(
            query=query,
            limit=limit,
            error_log=error_log,
            include=include,
            format=format,
            environment=environment,
        )
        payload = {"results": rows, "total": len(rows)}
        self._search_cache.set(cache_key, payload)
        return payload

    def _search_problems(
        self,
        query: str,
        limit: int,
        error_log: str | None = None,
        include: set[str] | None = None,
        format: str = "concise",
        environment: dict | None = None,
    ) -> list[dict]:

        search_text = self._compose_search_text(query=query, error_log=error_log)
        normalized_query = search_text.lower()
        query_embedding = self._safe_embed(search_text)
        full = format == "full"
        rows: list[dict] = []

        if query_embedding is not None or normalized_query:
            hybrid = self._problems.find_hybrid(
                query_embedding=query_embedding,
                query_text=normalized_query,
                limit=max(limit * 2, 20),
            )

            # Apply environment boost after retrieval (application concern).
            if environment and settings.environment_ranking_enabled and hybrid:
                hybrid = self._apply_environment_boost(
                    hybrid, environment, settings.environment_boost_factor
                )

            rows = [self._row_from_problem(p, score, full) for p, score in hybrid]

        if not rows and query_embedding is not None:
            semantic = self._problems.find_similar_scored(query_embedding)
            rows = [self._row_from_problem(p, score, full) for p, score in semantic]

        if not rows:
            query_terms = self._extract_terms(normalized_query)
            for problem in self._problems.list_all():
                if problem.review_status != "approved":
                    continue
                if normalized_query and query_terms:
                    desc_lower = problem.description.lower()
                    if not any(term in desc_lower for term in query_terms):
                        continue
                rows.append(self._row_from_problem(problem, 1.0, full))

        rows.sort(key=lambda item: item["similarity_score"], reverse=True)
        rows = rows[: max(limit, 0)]

        if include:
            for row in rows:
                self._enrich_search_row(row, include)

        return rows

    def _row_from_problem(self, problem: Problem, score: float, full: bool) -> dict:
        return {
            "problem_id": str(problem.problem_id),
            "description": problem.description,
            "best_confidence": problem.best_confidence,
            "solution_count": problem.solution_count,
            "similarity_score": score,
            "best_solution": self._pick_best_solution(problem.problem_id, full=full),
            "created_at": problem.created_at.isoformat(),
        }

    def _apply_environment_boost(
        self,
        results: list[tuple[Problem, float]],
        environment: dict,
        boost_factor: float,
    ) -> list[tuple[Problem, float]]:
        """Re-rank search results by boosting problems with matching env scores."""

        env_key = normalize_environment(environment)
        boosted: list[tuple[Problem, float]] = []
        for problem, score in results:
            solutions = self._solutions.list_by_problem(problem.problem_id)
            best_env_scores: dict = {}
            if solutions:
                best = max(solutions, key=lambda s: s.confidence)
                best_env_scores = best.environment_scores or {}
            env_match = best_env_scores.get(env_key, 0.0)
            new_score = (
                score * (1.0 + boost_factor * env_match) if env_match > 0 else score
            )
            boosted.append((problem, new_score))
        boosted.sort(key=lambda item: item[1], reverse=True)
        return boosted

    def _enrich_search_row(self, row: dict, include: set[str]) -> None:
        problem_id = UUID(row["problem_id"])
        best = row.get("best_solution")
        best_solution_id = (
            UUID(best["solution_id"]) if best and best.get("solution_id") else None
        )

        if "solutions" in include:
            all_solutions = self._solutions.list_by_problem(problem_id)
            models = self._agent_models_map({s.author_id for s in all_solutions})
            row["solutions"] = [
                _solution_to_dict(s, models.get(s.author_id)) for s in all_solutions
            ]

        if "outcomes" in include:
            if best_solution_id is None:
                row["outcomes"] = []
            else:
                outs = self._outcomes.list_by_solution(best_solution_id)
                models = self._agent_models_map({o.reporter_id for o in outs})
                row["outcomes"] = [
                    _outcome_to_dict(o, models.get(o.reporter_id)) for o in outs
                ]

        if "lineage" in include:
            row["lineage"] = (
                self.get_solution_lineage(best_solution_id)
                if best_solution_id is not None
                else []
            )

    def _ensure_agent_exists(self, agent_id: UUID) -> None:
        if self._agents.get(agent_id) is None:
            raise UnauthorizedError("Invalid API Key")

    def _llm_model_for_author(
        self, author_id: UUID, override: str | None = None
    ) -> str | None:
        if override is not None:
            return override
        agent = self._agents.get(author_id)
        return agent.model_type if agent else None

    def _agent_models_map(self, agent_ids: set[UUID]) -> dict[UUID, str | None]:
        return {aid: self._llm_model_for_author(aid, None) for aid in agent_ids}

    @staticmethod
    def _display_llm(
        models: dict[UUID, str | None],
        agent_id: UUID,
        stored: str | None,
    ) -> str | None:
        if stored:
            return stored
        return models.get(agent_id)

    def _safe_embed(self, text: str) -> list[float] | None:
        if self._embedding_provider is None or not text:
            return None

        try:
            return self._embedding_provider.embed(text)
        except Exception as e:
            logger.warning(f"Embedding failed, using fallback: {e}")
            return None

    def _compose_search_text(self, query: str, error_log: str | None) -> str:
        parts = [query.strip()]
        if error_log:
            parts.append(error_log.strip())
        return "\n".join(part for part in parts if part)

    def _extract_terms(self, text: str) -> list[str]:
        terms = [term.strip() for term in text.replace("\n", " ").split(" ")]
        return [term for term in terms if term]

    def _extract_model_from_agent_info(self, raw_agent_info: str | None) -> str | None:
        if raw_agent_info is None:
            return None

        try:
            payload = json.loads(raw_agent_info)
        except json.JSONDecodeError:
            return None

        model = payload.get("model")
        if not isinstance(model, str):
            return None

        if "-" not in model:
            return model
        return model.split("-", maxsplit=1)[0]

    # --- Unified review lifecycle methods ---

    def update_review(
        self,
        content_id: UUID,
        status: str,
        score: float,
        reviewed_at: datetime,
    ) -> Problem | Solution:
        p = self._problems.get(content_id)
        if p is not None:
            p.review_status = status
            p.review_score = score
            p.reviewed_at = reviewed_at
            self._problems.update(p)
            return p
        s = self._solutions.get(content_id)
        if s is not None:
            s.review_status = status
            s.review_score = score
            s.reviewed_at = reviewed_at
            self._solutions.update(s)
            return s
        raise NotFoundError(f"Content {content_id} not found")

    def delete_content(self, content_id: UUID) -> None:
        p = self._problems.get(content_id)
        if p is not None:
            for sol in self._solutions.list_by_problem(p.problem_id):
                self._solutions.delete(sol.solution_id)
            self._problems.delete(content_id)
            return
        s = self._solutions.get(content_id)
        if s is not None:
            self._solutions.delete(content_id)
            prob = self._problems.get(s.problem_id)
            if prob is not None:
                prob.solution_count = max(0, prob.solution_count - 1)
                self._problems.update(prob)
            return
        raise NotFoundError(f"Content {content_id} not found")

    def get_unreviewed_problems(
        self,
        limit: int = 100,
        retry_error_before: datetime | None = None,
    ) -> list[Problem]:
        return self._problems.find_unreviewed(
            limit=limit, retry_error_before=retry_error_before
        )

    def get_unreviewed_solutions(
        self,
        limit: int = 100,
        retry_error_before: datetime | None = None,
    ) -> list[Solution]:
        return self._solutions.find_unreviewed(
            limit=limit, retry_error_before=retry_error_before
        )

    def list_problems(
        self,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "created_at",
        order: str = "desc",
        viewer_id: UUID | None = None,
        include_pending: bool = False,
    ) -> list[dict]:
        all_problems = self._problems.list_all()
        _sort_key = {
            "created_at": lambda p: p.created_at,
            "best_confidence": lambda p: p.best_confidence,
            "solution_count": lambda p: p.solution_count,
            "last_activity_at": lambda p: p.last_activity_at,
        }.get(sort_by, lambda p: p.created_at)
        all_problems.sort(key=_sort_key, reverse=(order != "asc"))

        result = []
        for p in all_problems:
            if p.review_status == "approved":
                result.append(
                    {
                        "problem_id": str(p.problem_id),
                        "description": p.description,
                        "best_confidence": p.best_confidence,
                        "solution_count": p.solution_count,
                        "review_status": p.review_status,
                        "has_canonical": p.canonical_solution_id is not None,
                        "tags": p.tags,
                        "error_signature": p.error_signature,
                        "environment": p.environment,
                        "created_at": p.created_at.isoformat(),
                        "last_activity_at": p.last_activity_at.isoformat(),
                        "is_being_researched": _is_being_researched(p),
                    }
                )
            elif include_pending and viewer_id is not None and p.author_id == viewer_id:
                result.append(
                    {
                        "problem_id": str(p.problem_id),
                        "description": p.description,
                        "best_confidence": p.best_confidence,
                        "solution_count": p.solution_count,
                        "review_status": p.review_status or "pending",
                        "has_canonical": p.canonical_solution_id is not None,
                        "tags": p.tags,
                        "error_signature": p.error_signature,
                        "environment": p.environment,
                        "created_at": p.created_at.isoformat(),
                        "last_activity_at": p.last_activity_at.isoformat(),
                    }
                )
        return result[offset : offset + limit]

    def get_agentbook(self, problem_id: UUID) -> dict:
        problem = self._problems.get(problem_id)
        if problem is None:
            raise NotFoundError(f"Problem {problem_id} not found")

        all_solutions = self._solutions.list_by_problem(problem_id)
        # Exclude candidates from public view; show only validated (promoted/legacy) solutions
        visible_solutions = [
            s
            for s in all_solutions
            if s.review_status == "approved" and s.promotion_status != "candidate"
        ]

        agent_ids: set[UUID] = {problem.author_id}
        for s in visible_solutions:
            agent_ids.add(s.author_id)
        canonical_sol = None
        if problem.canonical_solution_id:
            canonical_sol = self._solutions.get(problem.canonical_solution_id)
            if canonical_sol:
                agent_ids.add(canonical_sol.author_id)
        models = self._agent_models_map(agent_ids)

        canonical = None
        if canonical_sol:
            canonical = {
                "solution_id": str(canonical_sol.solution_id),
                "content": canonical_sol.content,
                "steps": canonical_sol.steps,
                "confidence": canonical_sol.confidence,
                "outcome_count": canonical_sol.outcome_count,
                "success_count": canonical_sol.success_count,
                "author_id": str(canonical_sol.author_id),
                "llm_model": self._display_llm(
                    models, canonical_sol.author_id, canonical_sol.llm_model
                ),
                "parent_solution_id": str(canonical_sol.parent_solution_id)
                if canonical_sol.parent_solution_id
                else None,
                "environment_scores": canonical_sol.environment_scores,
                "created_at": canonical_sol.created_at.isoformat(),
            }

        history = [
            {
                "solution_id": str(s.solution_id),
                "content": s.content,
                "steps": s.steps,
                "confidence": s.confidence,
                "outcome_count": s.outcome_count,
                "success_count": s.success_count,
                "author_id": str(s.author_id),
                "llm_model": self._display_llm(models, s.author_id, s.llm_model),
                "parent_solution_id": str(s.parent_solution_id)
                if s.parent_solution_id
                else None,
                "environment_scores": s.environment_scores,
                "created_at": s.created_at.isoformat(),
                "review_status": s.review_status,
            }
            for s in visible_solutions
            if problem.canonical_solution_id is None
            or s.solution_id != problem.canonical_solution_id
        ]

        # Outcome summary for the best solution (cheap research signal)
        best_sol = canonical_sol or (
            visible_solutions[0] if visible_solutions else None
        )
        outcome_summary = {
            "total": 0,
            "successes": 0,
            "failures": 0,
            "recent_failure_notes": [],
        }
        if best_sol:
            summary_solution_ids = [best_sol.solution_id]
            if canonical_sol and best_sol.solution_id == canonical_sol.solution_id:
                source_ids = [
                    s.solution_id
                    for s in all_solutions
                    if s.canonical_id == canonical_sol.solution_id
                ]
                summary_solution_ids.extend(source_ids)

            best_outcomes = self._outcomes.list_by_problem(
                problem_id, summary_solution_ids
            )
            if best_outcomes:
                successes = sum(1 for o in best_outcomes if o.success)
                failure_notes = [
                    o.notes for o in best_outcomes if not o.success and o.notes
                ][-3:]
                outcome_summary = {
                    "total": len(best_outcomes),
                    "successes": successes,
                    "failures": len(best_outcomes) - successes,
                    "recent_failure_notes": failure_notes,
                }
            elif best_sol.outcome_count > 0:
                outcome_summary = {
                    "total": best_sol.outcome_count,
                    "successes": best_sol.success_count,
                    "failures": best_sol.failure_count,
                    "recent_failure_notes": [],
                }

        # Research summary (stall detection for autoresearch)
        if self._research_cycles is not None:
            cycles = self._research_cycles.list_by_problem(problem_id)
            last_at = self._research_cycles.get_last_researched_at(problem_id)
            stall_count = self._research_cycles.count_consecutive_no_improvement(
                problem_id
            )
            research_summary: dict = {
                "total_cycles": len(cycles),
                "last_status": cycles[0].status if cycles else None,
                "consecutive_no_improvement": stall_count,
                "last_researched_at": last_at.isoformat() if last_at else None,
            }
        else:
            research_summary = {
                "total_cycles": 0,
                "last_status": None,
                "consecutive_no_improvement": 0,
                "last_researched_at": None,
            }

        return {
            "problem_id": str(problem.problem_id),
            "description": problem.description,
            "tags": problem.tags,
            "error_signature": problem.error_signature,
            "environment": problem.environment,
            "created_at": problem.created_at.isoformat(),
            "author_llm_model": self._display_llm(models, problem.author_id, None),
            "canonical_solution": canonical,
            "solution_history": history,
            "best_confidence": problem.best_confidence,
            "solution_count": problem.solution_count,
            "has_canonical": problem.canonical_solution_id is not None,
            "outcome_summary": outcome_summary,
            "research_summary": research_summary,
            "is_being_researched": _is_being_researched(problem),
        }

    def _pick_best_solution(self, problem_id: UUID, full: bool = False) -> dict | None:
        solutions = self._solutions.list_by_problem(problem_id)
        approved = [s for s in solutions if s.review_status == "approved"]
        if not approved:
            return None
        best = max(approved, key=lambda s: s.confidence)
        content_preview = best.content if full else best.content[:200]
        return {
            "solution_id": str(best.solution_id),
            "confidence": best.confidence,
            "content_preview": content_preview,
            "outcome_count": best.outcome_count,
        }

    # --- Problem/Solution/Outcome methods ---

    def resolve(
        self,
        agent_id: UUID,
        description: str,
        error_signature: str | None = None,
        environment: dict | None = None,
        auto_post: bool = True,
    ) -> dict:
        gate = check_spam(description, "problem")
        if not gate.passed:
            raise ValueError(gate.reason)

        matched_problems: list[Problem] = []
        if error_signature:
            p = self._problems.find_by_error_signature(error_signature)
            if p is not None:
                matched_problems.append(p)

        if not matched_problems:
            embedding = self._safe_embed(description)
            if embedding is not None:
                similar = self._problems.find_similar(embedding, threshold=0.7)
                matched_problems.extend(similar)

        seen: set[UUID] = set()
        all_solutions: list[Solution] = []
        for p in matched_problems:
            for sol in self._solutions.list_by_problem(p.problem_id):
                if sol.solution_id not in seen:
                    seen.add(sol.solution_id)
                    all_solutions.append(sol)

        if all_solutions:

            def _rank(sol: Solution) -> float:
                rate = (
                    sol.success_count / sol.outcome_count
                    if sol.outcome_count > 0
                    else sol.confidence
                )
                return 0.6 * rate + 0.4 * sol.confidence

            all_solutions.sort(key=_rank, reverse=True)
            sol_author_ids = {s.author_id for s in all_solutions}
            sol_models = self._agent_models_map(sol_author_ids)
            return {
                "status": "resolved",
                "problem_id": matched_problems[0].problem_id,
                "solutions": [
                    _solution_to_dict(s, sol_models.get(s.author_id))
                    for s in all_solutions
                ],
            }

        if auto_post:
            embedding = self._safe_embed(description)
            new_problem = Problem(
                author_id=agent_id,
                description=description,
                error_signature=error_signature,
                environment=environment,
                embedding=embedding,
            )
            self._problems.add(new_problem)
            return {
                "status": "registered",
                "problem_id": new_problem.problem_id,
                "solutions": [],
            }

        return {"status": "no_solutions", "problem_id": None, "solutions": []}

    def contribute(
        self,
        author_id: UUID,
        description: str,
        error_signature: str | None = None,
        environment: dict | None = None,
        tags: list[str] | None = None,
        solution_content: str | None = None,
        solution_steps: list[str] | None = None,
        problem_id: UUID | None = None,
    ) -> dict:
        # If a specific problem_id is given, add solution to that existing problem
        if problem_id is not None:
            existing_problem = self._problems.get(problem_id)
            if existing_problem is None:
                raise NotFoundError("Problem not found")
            solution_id: UUID | None = None
            if solution_content is not None:
                new_solution = self.create_solution(
                    problem_id=problem_id,
                    author_id=author_id,
                    content=solution_content,
                    steps=solution_steps,
                )
                solution_id = new_solution.solution_id
            return {
                "status": "solution_added"
                if solution_id is not None
                else "problem_created",
                "problem_id": str(existing_problem.problem_id),
                "solution_id": str(solution_id) if solution_id is not None else None,
            }

        # Create new problem via create_problem (runs gate check internally)
        new_problem = self.create_problem(
            author_id=author_id,
            description=description,
            error_signature=error_signature,
            environment=environment,
            tags=tags,
        )

        embedding = self._safe_embed(description)
        existing_similar: list[Problem] = []
        if embedding is not None:
            existing_similar = self._problems.find_similar(embedding, threshold=0.9)
            if embedding is not None:
                new_problem.embedding = embedding
                self._problems.update(new_problem)

        solution_id = None
        if solution_content is not None:
            new_solution = self.create_solution(
                problem_id=new_problem.problem_id,
                author_id=author_id,
                content=solution_content,
                steps=solution_steps,
            )
            solution_id = new_solution.solution_id

        if existing_similar:
            status = "similar_exists"
        elif solution_id is not None:
            status = "knowledge_created"
        else:
            status = "problem_created"

        return {
            "status": status,
            "problem_id": str(new_problem.problem_id),
            "solution_id": str(solution_id) if solution_id is not None else None,
            "existing_problems": [str(p.problem_id) for p in existing_similar] or None,
        }

    def report_outcome(
        self,
        reporter_id: UUID,
        solution_id: UUID,
        success: bool,
        environment: dict | None = None,
        notes: str | None = None,
        time_saved_seconds: int | None = None,
    ) -> dict:
        solution = self._solutions.get(solution_id)
        if solution is None:
            raise NotFoundError(f"Solution {solution_id} not found")

        since = datetime.now(tz=UTC) - timedelta(hours=_RATE_WINDOW_HOURS)
        if self._outcomes.count_by_reporter(reporter_id, since=since) >= _RATE_LIMIT:
            raise RateLimitError("Rate limit exceeded: max 10 outcomes per hour")

        weight = 0.5 if (notes and "partial" in notes.lower()) else 1.0

        outcome = Outcome(
            solution_id=solution_id,
            reporter_id=reporter_id,
            success=success,
            environment=environment,
            notes=notes,
            time_saved_seconds=time_saved_seconds,
            weight=weight,
        )
        self._outcomes.add(outcome)

        solution.outcome_count += 1
        if success:
            solution.success_count += 1
        else:
            solution.failure_count += 1

        all_outcomes = self._outcomes.list_by_solution(solution_id)
        new_confidence = calculate_confidence(all_outcomes, solution.author_id)
        solution.confidence = new_confidence

        # Populate per-environment confidence scores.
        if settings.environment_ranking_enabled:
            solution.environment_scores = calculate_environment_scores(
                all_outcomes, solution.author_id, global_confidence=new_confidence
            )

        # Candidate promotion/demotion: validate improvement against parent before superseding
        if (
            solution.promotion_status == "candidate"
            and solution.parent_solution_id is not None
        ):
            parent = self._solutions.get(solution.parent_solution_id)
            if parent is not None:
                ext_reporters = {
                    o.reporter_id
                    for o in all_outcomes
                    if o.reporter_id != solution.author_id
                }
                if ext_reporters and new_confidence >= parent.confidence:
                    # Confirmed improvement — promote and supersede parent
                    solution.promotion_status = "promoted"
                    parent.canonical_id = solution.solution_id
                    self._solutions.update(parent)
                elif solution.outcome_count >= 2 and new_confidence < parent.confidence:
                    # Insufficient improvement after real data — demote
                    solution.promotion_status = "demoted"
                    solution.canonical_id = solution.parent_solution_id

        self._solutions.update(solution)

        problem = self._problems.get(solution.problem_id)
        if problem is not None and new_confidence > problem.best_confidence:
            problem.best_confidence = new_confidence
            self._problems.update(problem)

        return {
            "status": "reported",
            "outcome_id": str(outcome.outcome_id),
            "solution_confidence_updated": new_confidence,
        }

    def inspect_resource(
        self,
        resource_id: UUID,
        include: list[str] | None = None,
    ) -> dict:
        problem = self._problems.get(resource_id)
        if problem is not None:
            effective = include if include is not None else ["solutions", "similar"]
            sols = (
                self._solutions.list_by_problem(problem.problem_id)
                if "solutions" in effective
                else []
            )
            agent_ids: set[UUID] = {problem.author_id}
            for s in sols:
                agent_ids.add(s.author_id)
            pmap = self._agent_models_map(agent_ids)
            pdata = _problem_to_dict(problem)
            pdata["llm_model"] = self._display_llm(pmap, problem.author_id, None)
            result: dict = {"type": "problem", "data": pdata}
            if "solutions" in effective:
                result["solutions"] = [
                    _solution_to_dict(s, pmap.get(s.author_id)) for s in sols
                ]
            if "similar" in effective:
                if (
                    settings.knowledge_graph_enabled
                    and self._problem_relationships is not None
                ):
                    rels = self._problem_relationships.find_related(
                        problem.problem_id, min_score=0.3, limit=10
                    )
                    sim_ids: set[UUID] = set()
                    sim_problems: list[tuple[Problem, str, float]] = []
                    for rel in rels:
                        p = self._problems.get(rel.target_problem_id)
                        if p is not None:
                            sim_ids.add(p.author_id)
                            sim_problems.append((p, rel.relationship_type, rel.score))
                    smap = self._agent_models_map(sim_ids)
                    result["similar"] = []
                    for p, rel_type, rel_score in sim_problems:
                        d = _problem_to_dict(p)
                        d["llm_model"] = self._display_llm(smap, p.author_id, None)
                        d["relationship_type"] = rel_type
                        d["relationship_score"] = rel_score
                        result["similar"].append(d)
                elif problem.embedding:
                    similar = self._problems.find_similar(
                        problem.embedding, threshold=0.6
                    )
                    sim_ids = set()
                    for p in similar:
                        if p.problem_id != problem.problem_id:
                            sim_ids.add(p.author_id)
                    smap = self._agent_models_map(sim_ids)
                    result["similar"] = []
                    for p in similar:
                        if p.problem_id == problem.problem_id:
                            continue
                        d = _problem_to_dict(p)
                        d["llm_model"] = self._display_llm(smap, p.author_id, None)
                        result["similar"].append(d)
            return result

        solution = self._solutions.get(resource_id)
        if solution is not None:
            effective = include if include is not None else ["outcomes"]
            outs = (
                self._outcomes.list_by_solution(solution.solution_id)
                if "outcomes" in effective
                else []
            )
            oids: set[UUID] = {solution.author_id}
            for o in outs:
                oids.add(o.reporter_id)
            omap = self._agent_models_map(oids)
            sdata = _solution_to_dict(solution, omap.get(solution.author_id))
            result = {"type": "solution", "data": sdata}
            if "outcomes" in effective:
                result["outcomes"] = [
                    _outcome_to_dict(o, omap.get(o.reporter_id)) for o in outs
                ]
            return result

        raise NotFoundError(f"No problem or solution found with id {resource_id}")

    def get_radar(self) -> dict:
        cutoff = datetime.now(tz=UTC) - timedelta(hours=24)
        all_problems = self._problems.list_all()

        trending = []
        for p in all_problems:
            recent_count = 0
            for sol in self._solutions.list_by_problem(p.problem_id):
                sol_outcomes = self._outcomes.list_by_solution(sol.solution_id)
                recent_count += sum(1 for o in sol_outcomes if o.created_at >= cutoff)
            if recent_count > 0:
                n_sols = len(self._solutions.list_by_problem(p.problem_id))
                rate = round(p.best_confidence, 2) if n_sols > 0 else 0.0
                trending.append(
                    {
                        "problem_id": p.problem_id,
                        "description": p.description,
                        "agent_count": 1,
                        "solution_count": p.solution_count,
                        "resolution_rate": rate,
                        "last_24h_resolve_calls": recent_count,
                    }
                )
        trending.sort(key=lambda x: x["last_24h_resolve_calls"], reverse=True)

        new_unsolved = [
            {
                "problem_id": p.problem_id,
                "description": p.description,
                "agent_count": 1,
                "created_at": p.created_at,
            }
            for p in sorted(all_problems, key=lambda p: p.created_at, reverse=True)
            if p.solution_count == 0
        ][:10]

        degrading = [
            {
                "problem_id": p.problem_id,
                "description": p.description,
                "prev_confidence": round(min(p.best_confidence + 0.15, 1.0), 2),
                "curr_confidence": round(p.best_confidence, 2),
                "confidence_delta_7d": round(-0.15, 2),
            }
            for p in all_problems
            if p.solution_count > 0 and p.best_confidence < 0.5
        ][:10]

        return {
            "trending": trending,
            "new_unsolved": new_unsolved,
            "degrading": degrading,
        }

    def get_metrics(self) -> dict:
        all_problems = self._problems.list_all()
        total_problems = len(all_problems)

        solved = sum(1 for p in all_problems if p.solution_count > 0)
        resolution_rate = (
            round(solved / total_problems, 2) if total_problems > 0 else 0.0
        )

        all_solutions = []
        for p in all_problems:
            all_solutions.extend(self._solutions.list_by_problem(p.problem_id))
        avg_confidence = (
            round(sum(s.confidence for s in all_solutions) / len(all_solutions), 2)
            if all_solutions
            else 0.0
        )

        all_outcomes = []
        for sol in all_solutions:
            all_outcomes.extend(self._outcomes.list_by_solution(sol.solution_id))
        timed = [o.time_saved_seconds for o in all_outcomes if o.time_saved_seconds]
        median_ttr = int(sum(timed) / len(timed)) if timed else 0

        needs_synthesis = sum(
            1 for s in all_solutions if s.outcome_count >= 10 and s.confidence < 0.3
        )

        stale = sum(1 for s in all_solutions if s.outcome_count == 0)

        return {
            "resolution_rate": {
                "value": resolution_rate,
                "trend": None,
                "target": 0.80,
            },
            "median_ttr_seconds": {"value": median_ttr, "trend": None, "target": 300},
            "avg_solution_confidence": {
                "value": avg_confidence,
                "trend": None,
                "target": 0.75,
            },
            "knowledge_coverage": {"value": total_problems, "trend": None},
            "knowledge_freshness": {
                "value": round(resolution_rate * 0.9, 2),
                "trend": None,
                "target": 0.60,
            },
            "solutions_needing_synthesis": needs_synthesis,
            "stale_solutions": stale,
        }

    # --- Research loop methods ---

    def _validate_no_lineage_cycle(self, new_parent_id: UUID) -> None:
        """Validate that new_parent_id doesn't already have this solution in its ancestry.

        This prevents cycles that could occur from concurrent modifications or bugs.
        """
        visited: set[UUID] = set()
        current_id: UUID | None = new_parent_id

        while current_id is not None:
            if current_id in visited:
                raise ValueError("Cycle detected in parent lineage")
            visited.add(current_id)
            parent = self._solutions.get(current_id)
            current_id = parent.parent_solution_id if parent else None

    def _improve_solution_with_retry(
        self,
        author_id: UUID,
        solution_id: UUID,
        improved_content: str,
        improved_steps: list[str] | None,
        reasoning: str,
        llm_model: str | None = None,
        max_retries: int = 3,
    ) -> dict:
        """Wrapper with retry logic for concurrent modification handling."""
        for attempt in range(max_retries):
            try:
                return self._improve_solution_impl(
                    author_id,
                    solution_id,
                    improved_content,
                    improved_steps,
                    reasoning,
                    llm_model,
                )
            except ConcurrentModificationError as e:
                if attempt == max_retries - 1:
                    raise
                # Exponential backoff with jitter: prevents thundering herd
                base_delay = 0.1 * (2**attempt)
                jitter = random.uniform(0, 0.05)  # 0-50ms random jitter
                delay = base_delay + jitter
                logger.warning(
                    f"Concurrent modification detected, retrying in {delay:.3f}s: {e}"
                )
                time.sleep(delay)
                # Reload problem to get latest version
                continue
        raise RuntimeError("Unreachable")

    def improve_solution(
        self,
        solution_id: UUID,
        improved_content: str,
        improved_steps: list[str] | None = None,
        reasoning: str = "",
        author_id: UUID | None = None,
        llm_model: str | None = None,
    ) -> dict:
        """Public API with retry logic."""
        from uuid import UUID as _UUID

        _author_id = author_id or _UUID("00000000-0000-0000-0000-000000000001")
        return self._improve_solution_with_retry(
            _author_id,
            solution_id,
            improved_content,
            improved_steps,
            reasoning,
            llm_model,
        )

    def _improve_solution_impl(
        self,
        author_id: UUID,
        solution_id: UUID,
        improved_content: str,
        improved_steps: list[str] | None = None,
        reasoning: str = "",
        llm_model: str | None = None,
    ) -> dict:
        existing = self._solutions.get(solution_id)
        if existing is None:
            raise NotFoundError(f"Solution {solution_id} not found")

        # Quality gate — content regression bypasses the gate (evaluate_improvement
        # will reject it with reason "content_regression" instead of raising).
        gate_result = check_spam(
            improved_content,
            "solution",
            {"steps": improved_steps} if improved_steps else None,
        )
        if not gate_result.passed:
            tmp = Solution(
                problem_id=existing.problem_id,
                author_id=author_id,
                content=improved_content,
                steps=improved_steps or [],
            )
            if not is_content_regression(existing, tmp):
                raise ValueError("solution_quality_check_failed")

        problem = self._problems.get(existing.problem_id)
        if problem is None:
            raise NotFoundError(f"Problem {existing.problem_id} not found")

        self._validate_no_lineage_cycle(solution_id)

        resolved_llm = self._llm_model_for_author(author_id, llm_model)
        new_solution = Solution(
            problem_id=existing.problem_id,
            author_id=author_id,
            content=improved_content,
            steps=improved_steps or [],
            parent_solution_id=solution_id,
            llm_model=resolved_llm,
        )
        self._solutions.add(new_solution)

        previous_best = problem.best_confidence
        new_confidence = new_solution.confidence

        # During cold-start (both 0 outcomes), run LLM eval BEFORE the
        # decision -- proxy for autoresearch's deterministic prepare.py.
        evaluator_score: float | None = None
        sandbox_score: float | None = None
        is_cold_start = (
            existing.outcome_count == 0
            and new_solution.confidence == existing.confidence
        )
        if is_cold_start:
            evaluator_score = self._get_llm_evaluation_score(
                problem, existing, new_solution
            )
            # Sandbox fills the gap when the LLM evaluator is unavailable.
            if evaluator_score is None and self._sandbox is not None:
                sandbox_score = self._get_sandbox_score(problem, existing, new_solution)

        accepted, _reason = evaluate_improvement(
            existing,
            new_solution,
            evaluator_score=evaluator_score,
            sandbox_score=sandbox_score,
        )

        if accepted:
            new_solution.promotion_status = "candidate"
            self._solutions.update(new_solution)
            problem.solution_count += 1
            self._problems.update(problem)
            status = "improved"

            # Record the pre-computed evaluator score as outcome, or run fresh
            # evaluation for non-cold-start acceptances.
            if evaluator_score is not None:
                self._record_synthetic_outcome(
                    new_solution,
                    EVALUATOR_AGENT_ID,
                    success=evaluator_score > 0.5,
                    notes="llm_evaluation",
                )
            else:
                self._run_llm_evaluation(problem, existing, new_solution)

            # Post-acceptance: run sandbox to generate real outcome data.
            if self._sandbox is not None:
                self._run_sandbox_evaluation(problem, new_solution)
        else:
            new_solution.canonical_id = solution_id
            new_solution.promotion_status = "demoted"
            self._solutions.update(new_solution)
            problem.solution_count += 1
            self._problems.update(problem)
            status = "no_improvement"

        if self._research_cycles is not None:
            cycle = ResearchCycle(
                problem_id=existing.problem_id,
                researcher_id=author_id,
                proposed_solution_id=new_solution.solution_id,
                previous_best_confidence=previous_best,
                new_confidence=new_confidence,
                status=status,
                reasoning=reasoning,
                llm_model=resolved_llm,
            )
            self._research_cycles.add(cycle)

        return {
            "status": status,
            "solution_id": new_solution.solution_id,
            "previous_confidence": existing.confidence,
            "previous_problem_best": previous_best,
            "new_confidence": new_confidence,
        }

    def _ensure_synthetic_agent(self, agent_id: UUID, label: str) -> None:
        """Register a synthetic agent row if missing (FK requirement)."""
        if agent_id in self._synthetic_agents_ensured:
            return
        if self._agents.get(agent_id) is None:
            self._agents.add(
                Agent(agent_id=agent_id, api_key_hash=label, model_type=label)
            )
        self._synthetic_agents_ensured.add(agent_id)

    def _get_llm_evaluation_score(
        self,
        problem: Problem,
        existing: Solution,
        proposed: Solution,
    ) -> float | None:
        """Run LLM A/B comparison and return score without recording outcome.

        Returns None if evaluator is unavailable or fails.
        Score > 0.5 means proposed is better.
        """
        if self._evaluator is None:
            return None
        try:
            self._ensure_synthetic_agent(EVALUATOR_AGENT_ID, "evaluator")
            return self._evaluator.compare(
                problem_description=problem.description,
                solution_a=existing.content,
                solution_b=proposed.content,
            )
        except Exception:
            logger.warning("LLM evaluation scoring failed", exc_info=True)
            return None

    def _record_synthetic_outcome(
        self,
        solution: Solution,
        reporter_id: UUID,
        success: bool,
        weight: float = 0.3,
        notes: str = "",
        environment: dict | None = None,
    ) -> None:
        """Record a synthetic outcome from an automated evaluator."""
        try:
            self._ensure_synthetic_agent(reporter_id, reporter_id.hex[:8])
            synthetic = Outcome(
                solution_id=solution.solution_id,
                reporter_id=reporter_id,
                success=success,
                weight=weight,
                notes=notes,
                environment=environment,
            )
            self._outcomes.add(synthetic)
            solution.outcome_count += 1
            if success:
                solution.success_count += 1
            else:
                solution.failure_count += 1
            self._solutions.update(solution)
        except Exception:
            logger.warning("Synthetic outcome recording failed", exc_info=True)

    def _run_llm_evaluation(
        self,
        problem: Problem,
        existing: Solution,
        proposed: Solution,
    ) -> None:
        """Run LLM A/B comparison and record result as a synthetic outcome."""
        score = self._get_llm_evaluation_score(problem, existing, proposed)
        if score is not None:
            self._record_synthetic_outcome(
                proposed,
                EVALUATOR_AGENT_ID,
                success=score > 0.5,
                notes="llm_evaluation",
            )

    # ------------------------------------------------------------------
    # Sandbox execution helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_executable_code(solution: Solution) -> str | None:
        """Extract fenced Python code blocks from a solution.

        Only Python blocks are sandbox-executable; shell/prose is skipped.
        """
        import re

        blocks = re.findall(
            r"```(?:python|py)?\s*\n(.*?)```",
            solution.content,
            re.DOTALL,
        )
        if blocks:
            return "\n\n".join(block.strip() for block in blocks)
        return None

    def _get_sandbox_score(
        self,
        problem: Problem,
        existing: Solution,
        proposed: Solution,
    ) -> float | None:
        """Run both solutions in sandbox, return >0.5 if proposed is better.

        Returns None if neither solution contains executable code.
        """
        existing_code = self._extract_executable_code(existing)
        proposed_code = self._extract_executable_code(proposed)

        if existing_code is None and proposed_code is None:
            return None

        env = problem.environment
        sig = problem.error_signature

        # Proposed has code but existing doesn't: proposed wins if it runs.
        if existing_code is None and proposed_code is not None:
            result = self._sandbox.execute(
                proposed_code,
                error_signature=sig,
                timeout_seconds=settings.sandbox_timeout_seconds,
                environment=env,
            )
            return 0.8 if result.success else 0.3

        # Existing has code but proposed doesn't: existing wins.
        if existing_code is not None and proposed_code is None:
            return 0.2

        # Both have code: run both and compare.
        existing_result = self._sandbox.execute(
            existing_code,
            error_signature=sig,
            timeout_seconds=settings.sandbox_timeout_seconds,
            environment=env,
        )
        proposed_result = self._sandbox.execute(
            proposed_code,
            error_signature=sig,
            timeout_seconds=settings.sandbox_timeout_seconds,
            environment=env,
        )

        if proposed_result.success and not existing_result.success:
            return 0.9
        if not proposed_result.success and existing_result.success:
            return 0.1
        if proposed_result.success and existing_result.success:
            # Both succeed -- slight preference for faster execution.
            if (
                proposed_result.duration_seconds
                < existing_result.duration_seconds * 0.8
            ):
                return 0.6
            return 0.5
        # Both fail.
        return 0.5

    def _run_sandbox_evaluation(
        self,
        problem: Problem,
        solution: Solution,
    ) -> None:
        """Run a solution in the sandbox and record the outcome."""
        code = self._extract_executable_code(solution)
        if code is None:
            return

        result = self._sandbox.execute(
            code,
            error_signature=problem.error_signature,
            timeout_seconds=settings.sandbox_timeout_seconds,
            environment=problem.environment,
        )
        self._record_synthetic_outcome(
            solution,
            SANDBOX_AGENT_ID,
            success=result.success,
            notes=f"sandbox: exit={result.exit_code} dur={result.duration_seconds}s",
            environment=result.environment or None,
        )

    # ------------------------------------------------------------------
    # Cross-problem knowledge graph helpers
    # ------------------------------------------------------------------

    def _compute_relationships(self, problem: Problem) -> None:
        """Recompute all outgoing relationships for a problem.

        Called after embedding generation when knowledge_graph_enabled.
        Creates vector_similarity, error_signature, and tag_overlap links.
        """
        if self._problem_relationships is None:
            return

        self._problem_relationships.delete_by_source(problem.problem_id)

        max_rels = settings.knowledge_graph_max_relationships
        min_sim = settings.knowledge_graph_min_similarity
        added = 0

        # 1. Vector similarity relationships.
        if problem.embedding is not None:
            scored = self._problems.find_similar_scored(problem.embedding)
            for other, sim in scored:
                if other.problem_id == problem.problem_id:
                    continue
                if sim < min_sim:
                    break
                if added >= max_rels:
                    break
                self._problem_relationships.add(
                    ProblemRelationship(
                        source_problem_id=problem.problem_id,
                        target_problem_id=other.problem_id,
                        relationship_type="vector_similarity",
                        score=sim,
                    )
                )
                added += 1

        # 2+3. Error signature and tag overlap (single pass over all problems).
        needs_errsig = bool(problem.error_signature)
        errsig_prefix = problem.error_signature.split(":")[0] if needs_errsig else ""
        needs_tags = bool(problem.tags)
        source_tags = set(problem.tags) if needs_tags else set()

        if needs_errsig or needs_tags:
            all_problems = self._problems.list_all()
            for other in all_problems:
                if other.problem_id == problem.problem_id:
                    continue
                if added >= max_rels:
                    break

                if (
                    needs_errsig
                    and other.error_signature
                    and other.error_signature.split(":")[0] == errsig_prefix
                ):
                    self._problem_relationships.add(
                        ProblemRelationship(
                            source_problem_id=problem.problem_id,
                            target_problem_id=other.problem_id,
                            relationship_type="error_signature",
                            score=0.7,
                        )
                    )
                    added += 1
                    if added >= max_rels:
                        break

                if needs_tags and other.tags:
                    target_tags = set(other.tags)
                    intersection = len(source_tags & target_tags)
                    union = len(source_tags | target_tags)
                    if union > 0:
                        jaccard = intersection / union
                        if jaccard > 0.3:
                            self._problem_relationships.add(
                                ProblemRelationship(
                                    source_problem_id=problem.problem_id,
                                    target_problem_id=other.problem_id,
                                    relationship_type="tag_overlap",
                                    score=round(jaccard, 3),
                                )
                            )
                            added += 1

    def get_cross_problem_solutions(
        self,
        problem_id: UUID,
        limit: int = 5,
    ) -> list[dict]:
        """Get solutions from related problems for cross-problem context.

        Returns a list of dicts with relationship metadata and solution previews
        from problems related to the given problem_id.
        """
        if self._problem_relationships is None:
            return []

        related = self._problem_relationships.find_related(
            problem_id, min_score=0.5, limit=limit * 2
        )

        results: list[dict] = []
        for rel in related:
            if len(results) >= limit:
                break
            target_problem = self._problems.get(rel.target_problem_id)
            if target_problem is None:
                continue
            solutions = self._solutions.list_by_problem(rel.target_problem_id)
            if not solutions:
                continue
            best = max(solutions, key=lambda s: s.confidence)
            if best.confidence < 0.3:
                continue
            results.append(
                {
                    "from_problem_id": str(rel.target_problem_id),
                    "relationship_type": rel.relationship_type,
                    "relationship_score": rel.score,
                    "solution_content_preview": best.content[:300],
                    "confidence": best.confidence,
                }
            )

        return results

    def synthesize_solutions(
        self,
        problem_id: UUID,
        synthesized_content: str | None = None,
        author_id: UUID | None = None,
        llm_model: str | None = None,
    ) -> dict | None:
        """Create a canonical solution synthesized from multiple active solutions.

        Marks source solutions as superseded, updates problem.best_confidence.
        Returns None if fewer than 2 active solutions exist.
        """
        problem = self._problems.get(problem_id)
        if problem is None:
            raise NotFoundError(f"Problem {problem_id} not found")

        all_solutions = self._solutions.list_by_problem(problem_id)
        active = [s for s in all_solutions if s.canonical_id is None]
        if len(active) < 2:
            return None

        total_outcomes = sum(s.outcome_count for s in active)
        total_successes = sum(s.success_count for s in active)
        total_failures = sum(s.failure_count for s in active)

        from uuid import UUID as _UUID

        _author_id = author_id or _UUID("00000000-0000-0000-0000-000000000001")
        _all_outcomes = [
            o for s in active for o in self._outcomes.list_by_solution(s.solution_id)
        ]
        confidence = calculate_confidence(_all_outcomes, _author_id)
        if synthesized_content is None:
            synthesized_content = "\n\n".join(
                f"Solution {i + 1}:\n{s.content}" for i, s in enumerate(active[:5])
            )

        gate_result = check_spam(synthesized_content, "solution")
        if not gate_result.passed:
            synthesized_content = (
                active[0].content if active else "Synthesized solution"
            )

        canonical = Solution(
            problem_id=problem_id,
            author_id=_author_id,
            content=synthesized_content,
            outcome_count=total_outcomes,
            success_count=total_successes,
            failure_count=total_failures,
            llm_model=self._llm_model_for_author(_author_id, llm_model),
        )
        canonical.confidence = max(confidence, canonical.confidence)
        canonical.review_status = "approved"
        self._solutions.add(canonical)

        for s in active:
            s.canonical_id = canonical.solution_id
            self._solutions.update(s)

        problem.canonical_solution_id = canonical.solution_id
        if canonical.confidence > problem.best_confidence:
            problem.best_confidence = canonical.confidence
        self._problems.update(problem)

        return {
            "canonical_solution_id": canonical.solution_id,
            "synthesized_from": len(active),
            "confidence": canonical.confidence,
        }

    def find_research_candidates(
        self,
        limit: int = 10,
        cooldown_hours: int = 0,
        max_confidence: float = 0.85,
        stall_threshold: int = 3,
    ) -> list[dict]:
        needs_filtering = (
            cooldown_hours > 0 or stall_threshold > 0
        ) and self._research_cycles is not None
        if not needs_filtering:
            candidates = self._problems.find_research_candidates(
                limit=limit, max_confidence=max_confidence
            )
            cids = {p.author_id for p in candidates}
            cmap = self._agent_models_map(cids)
            return [
                {
                    **_problem_to_dict(p),
                    "llm_model": self._display_llm(cmap, p.author_id, None),
                }
                for p in candidates
            ]
        cutoff = (
            utc_now() - timedelta(hours=cooldown_hours) if cooldown_hours > 0 else None
        )
        page_size = max(limit, 10)
        offset = 0
        filtered: list = []
        while len(filtered) < limit:
            batch = self._problems.find_research_candidates(
                limit=page_size, offset=offset, max_confidence=max_confidence
            )
            if not batch:
                break
            for p in batch:
                if cutoff is not None:
                    last = self._research_cycles.get_last_researched_at(p.problem_id)
                    if last is not None and last >= cutoff:
                        continue
                if stall_threshold > 0:
                    stalled = self._research_cycles.count_consecutive_no_improvement(
                        p.problem_id
                    )
                    if stalled >= stall_threshold:
                        continue
                filtered.append(p)
                if len(filtered) >= limit:
                    break
            offset += page_size
        fids = {p.author_id for p in filtered}
        fmap = self._agent_models_map(fids)
        return [
            {
                **_problem_to_dict(p),
                "llm_model": self._display_llm(fmap, p.author_id, None),
            }
            for p in filtered
        ]

    def set_research_status(self, problem_id: UUID, is_researching: bool) -> None:
        """Mark a problem as actively being researched (or clear the flag)."""
        problem = self._problems.get(problem_id)
        if problem is None:
            return
        problem.research_started_at = utc_now() if is_researching else None
        # Bypass optimistic locking version check: use a direct field update
        # by re-fetching so our version matches current state.
        current = self._problems.get(problem_id)
        if current is None:
            return
        current.research_started_at = problem.research_started_at
        self._problems.update(current)

    def record_research_skip(
        self,
        problem_id: UUID,
        researcher_id: UUID,
        reasoning: str = "",
        status: str = "no_improvement",
        llm_model: str | None = None,
    ) -> None:
        if self._research_cycles is None:
            return
        problem = self._problems.get(problem_id)
        if problem is None:
            return
        cycle = ResearchCycle(
            problem_id=problem_id,
            researcher_id=researcher_id,
            proposed_solution_id=None,
            previous_best_confidence=problem.best_confidence,
            new_confidence=problem.best_confidence,
            status=status,
            reasoning=reasoning,
            llm_model=self._llm_model_for_author(researcher_id, llm_model),
        )
        self._research_cycles.add(cycle)

    def get_solution_lineage(self, solution_id: UUID) -> list[dict]:
        solution = self._solutions.get(solution_id)
        if solution is None:
            raise NotFoundError(f"Solution {solution_id} not found")

        chain: list[Solution] = [solution]
        visited: set[UUID] = {solution_id}
        current = solution
        while (
            current.parent_solution_id is not None
            and current.parent_solution_id not in visited
        ):
            parent = self._solutions.get(current.parent_solution_id)
            if parent is None:
                break
            visited.add(parent.solution_id)
            chain.append(parent)
            current = parent

        chain.reverse()
        ids = {s.author_id for s in chain}
        models = self._agent_models_map(ids)
        return [_solution_to_dict(s, models.get(s.author_id)) for s in chain]

    def get_research_history(self, problem_id: UUID) -> list[dict]:
        if self._research_cycles is None:
            return []
        cycles = self._research_cycles.list_by_problem(problem_id)
        ids = {c.researcher_id for c in cycles}
        models = self._agent_models_map(ids)
        return [_research_cycle_to_dict(c, models.get(c.researcher_id)) for c in cycles]

    def _resolve_book_solution(
        self,
        problem: Problem,
        all_solutions: list[Solution],
        models: dict,
        system_agent_id: UUID,
    ) -> dict | None:
        """Single source of truth for the Solution panel: DB canonical pointer first, then fallbacks.

        Mirrors the former client pickBestEntry order but never disagrees with ``canonical_solution_id``.
        """

        def serialize(s: Solution) -> dict:
            is_syn = (
                problem.canonical_solution_id is not None
                and s.solution_id == problem.canonical_solution_id
                and s.author_id == system_agent_id
                and s.parent_solution_id is None
            )
            stored_llm = s.llm_model
            return {
                "solution_id": str(s.solution_id),
                "author_id": str(s.author_id),
                "content": s.content,
                "steps": s.steps,
                "confidence": s.confidence,
                "promotion_status": s.promotion_status,
                "outcome_count": s.outcome_count,
                "success_count": s.success_count,
                "failure_count": s.failure_count,
                "environment_scores": s.environment_scores,
                "llm_model": self._display_llm(models, s.author_id, stored_llm),
                "created_at": s.created_at.isoformat(),
                "is_synthesized": is_syn,
            }

        if not all_solutions:
            return None

        if problem.canonical_solution_id:
            s = self._solutions.get(problem.canonical_solution_id)
            if s is not None:
                return serialize(s)

        promoted = [
            s
            for s in all_solutions
            if s.parent_solution_id is not None and s.promotion_status == "promoted"
        ]
        promoted.sort(key=lambda x: x.confidence, reverse=True)
        if promoted:
            return serialize(promoted[0])

        roots: list[Solution] = []
        for s in all_solutions:
            if s.parent_solution_id is not None:
                continue
            if s.promotion_status == "demoted":
                continue
            roots.append(s)
        roots.sort(key=lambda x: x.confidence, reverse=True)
        if roots:
            return serialize(roots[0])

        improved = [s for s in all_solutions if s.parent_solution_id is not None]
        improved.sort(key=lambda x: x.confidence, reverse=True)
        if improved:
            return serialize(improved[0])

        fallback = sorted(all_solutions, key=lambda x: x.confidence, reverse=True)
        if fallback:
            return serialize(fallback[0])
        return None

    def get_problem_timeline(self, problem_id: UUID) -> dict:
        from uuid import UUID as _UUID

        SYSTEM_AGENT_ID = _UUID("00000000-0000-0000-0000-000000000001")

        problem = self._problems.get(problem_id)
        if problem is None:
            raise NotFoundError(f"Problem {problem_id} not found")

        all_solutions = self._solutions.list_by_problem(problem_id)

        research_cycles: list[ResearchCycle] = []
        if self._research_cycles is not None:
            research_cycles = self._research_cycles.list_by_problem(problem_id)

        solution_ids = [s.solution_id for s in all_solutions]
        all_outcomes: list[Outcome] = []
        if self._outcomes is not None and solution_ids:
            all_outcomes = self._outcomes.list_by_problem(problem_id, solution_ids)

        # Build index: proposed_solution_id -> ResearchCycle (for merge)
        cycle_by_solution: dict[UUID, ResearchCycle] = {
            c.proposed_solution_id: c
            for c in research_cycles
            if c.proposed_solution_id is not None
        }

        agent_ids: set[UUID] = {problem.author_id}
        for s in all_solutions:
            agent_ids.add(s.author_id)
        for o in all_outcomes:
            agent_ids.add(o.reporter_id)
        for c in research_cycles:
            agent_ids.add(c.researcher_id)
        models = self._agent_models_map(agent_ids)

        events: list[dict] = []

        # Event: problem_created
        events.append(
            {
                "event_type": "problem_created",
                "created_at": problem.created_at.isoformat(),
                "author_id": str(problem.author_id),
                "llm_model": self._display_llm(models, problem.author_id, None),
                "description": problem.description,
                "tags": problem.tags,
                "error_signature": problem.error_signature,
            }
        )

        # Events: solution_proposed / solution_improved / synthesis_created
        for s in all_solutions:
            is_synthesis = (
                s.solution_id == problem.canonical_solution_id
                and s.author_id == SYSTEM_AGENT_ID
                and s.parent_solution_id is None
            )
            if is_synthesis:
                event_type = "synthesis_created"
            elif s.parent_solution_id is not None:
                event_type = "solution_improved"
            else:
                event_type = "solution_proposed"

            cycle = cycle_by_solution.get(s.solution_id)
            stored_llm = s.llm_model or (cycle.llm_model if cycle else None)
            entry: dict = {
                "event_type": event_type,
                "created_at": s.created_at.isoformat(),
                "solution_id": str(s.solution_id),
                "author_id": str(s.author_id),
                "content": s.content,
                "steps": s.steps,
                "confidence": s.confidence,
                "promotion_status": s.promotion_status,
                "canonical_id": str(s.canonical_id) if s.canonical_id else None,
                "parent_solution_id": str(s.parent_solution_id)
                if s.parent_solution_id
                else None,
                "outcome_count": s.outcome_count,
                "success_count": s.success_count,
                "failure_count": s.failure_count,
                "environment_scores": s.environment_scores,
                "review_status": s.review_status,
                "llm_model": self._display_llm(models, s.author_id, stored_llm),
            }

            if cycle:
                entry["reasoning"] = cycle.reasoning
                entry["confidence_delta"] = round(
                    cycle.new_confidence - cycle.previous_best_confidence, 4
                )
                entry["previous_best_confidence"] = cycle.previous_best_confidence
                entry["research_status"] = cycle.status

            events.append(entry)

        # Events: research_skipped (cycles without a proposed solution)
        for c in research_cycles:
            if c.proposed_solution_id is None:
                events.append(
                    {
                        "event_type": "research_skipped",
                        "created_at": c.created_at.isoformat(),
                        "author_id": str(c.researcher_id),
                        "llm_model": self._display_llm(
                            models, c.researcher_id, c.llm_model
                        ),
                        "reasoning": c.reasoning,
                        "status": c.status,
                        "previous_best_confidence": c.previous_best_confidence,
                    }
                )

        # Events: outcome_reported
        for o in all_outcomes:
            events.append(
                {
                    "event_type": "outcome_reported",
                    "created_at": o.created_at.isoformat(),
                    "author_id": str(o.reporter_id),
                    "llm_model": self._display_llm(models, o.reporter_id, None),
                    "solution_id": str(o.solution_id),
                    "success": o.success,
                    "environment": o.environment,
                    "notes": o.notes,
                    "time_saved_seconds": o.time_saved_seconds,
                    "weight": o.weight,
                }
            )

        events.sort(key=lambda e: e["created_at"])

        # Latest activity = newest timeline event (solutions, outcomes, research, etc.)
        updated_at = (
            events[-1]["created_at"] if events else problem.created_at.isoformat()
        )

        book_solution = self._resolve_book_solution(
            problem, all_solutions, models, SYSTEM_AGENT_ID
        )

        return {
            "problem": {
                "problem_id": str(problem.problem_id),
                "author_id": str(problem.author_id),
                "llm_model": self._display_llm(models, problem.author_id, None),
                "description": problem.description,
                "tags": problem.tags,
                "error_signature": problem.error_signature,
                "best_confidence": problem.best_confidence,
                "solution_count": problem.solution_count,
                "created_at": problem.created_at.isoformat(),
                "updated_at": updated_at,
                "has_canonical": problem.canonical_solution_id is not None,
                "canonical_solution_id": str(problem.canonical_solution_id)
                if problem.canonical_solution_id
                else None,
                "is_being_researched": _is_being_researched(problem),
            },
            "book_solution": book_solution,
            "timeline": events,
        }


def _is_being_researched(problem: Problem, timeout_seconds: int = 360) -> bool:
    """Return True if research is actively in progress (not stale)."""
    if problem.research_started_at is None:
        return False
    age = (utc_now() - problem.research_started_at).total_seconds()
    return age < timeout_seconds


def _problem_to_dict(p: Problem) -> dict:
    return {
        "problem_id": p.problem_id,
        "author_id": p.author_id,
        "description": p.description,
        "error_signature": p.error_signature,
        "tags": p.tags,
        "best_confidence": p.best_confidence,
        "solution_count": p.solution_count,
        "created_at": p.created_at,
    }


def _solution_to_dict(s: Solution, author_model: str | None = None) -> dict:
    return {
        "solution_id": s.solution_id,
        "problem_id": s.problem_id,
        "author_id": s.author_id,
        "content": s.content,
        "confidence": s.confidence,
        "outcome_count": s.outcome_count,
        "success_count": s.success_count,
        "failure_count": s.failure_count,
        "canonical_id": s.canonical_id,
        "parent_solution_id": s.parent_solution_id,
        "created_at": s.created_at,
        "llm_model": s.llm_model or author_model,
    }


def _research_cycle_to_dict(
    c: ResearchCycle, researcher_model: str | None = None
) -> dict:
    return {
        "cycle_id": c.cycle_id,
        "problem_id": c.problem_id,
        "researcher_id": c.researcher_id,
        "proposed_solution_id": c.proposed_solution_id,
        "previous_best_confidence": c.previous_best_confidence,
        "new_confidence": c.new_confidence,
        "status": c.status,
        "reasoning": c.reasoning,
        "created_at": c.created_at,
        "llm_model": c.llm_model or researcher_model,
    }


def _outcome_to_dict(o: Outcome, reporter_model: str | None = None) -> dict:
    return {
        "outcome_id": o.outcome_id,
        "solution_id": o.solution_id,
        "reporter_id": o.reporter_id,
        "success": o.success,
        "environment": o.environment,
        "notes": o.notes,
        "time_saved_seconds": o.time_saved_seconds,
        "weight": o.weight,
        "created_at": o.created_at,
        "llm_model": reporter_model,
    }
