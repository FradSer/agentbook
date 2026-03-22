from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.application.confidence import calculate_confidence
from app.application.errors import ConcurrentModificationError, NotFoundError, RateLimitError, UnauthorizedError
from app.application.gate import check_spam
from app.core.config import settings
from app.domain.models import Agent, Outcome, Problem, ResearchCycle, Solution, TokenTransaction, utc_now
from app.domain.repositories import (
    AgentRepository,
    OutcomeRepository,
    ProblemRepository,
    ResearchCycleRepository,
    SolutionRepository,
    TokenTransactionRepository,
)
from app.domain.services import EmbeddingProvider
from app.infrastructure.security import generate_api_key, hash_api_key

logger = logging.getLogger(__name__)

_RATE_LIMIT = 10
_RATE_WINDOW_HOURS = 1


class AgentbookService:
    def __init__(
        self,
        agents: AgentRepository,
        transactions: TokenTransactionRepository,
        embedding_provider: EmbeddingProvider | None = None,
        problems: ProblemRepository = None,
        solutions: SolutionRepository = None,
        outcomes: OutcomeRepository = None,
        research_cycles: ResearchCycleRepository = None,
    ) -> None:
        self._agents = agents
        self._transactions = transactions
        self._embedding_provider = embedding_provider
        self._problems = problems
        self._solutions = solutions
        self._outcomes = outcomes
        self._research_cycles = research_cycles

    def register_agent(self, model_type: str | None) -> tuple[Agent, str]:
        api_key = generate_api_key()
        agent = Agent(
            api_key_hash=hash_api_key(api_key),
            model_type=model_type,
            token_balance=settings.initial_token_balance,
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

    def get_balance(self, agent_id: UUID) -> dict:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise UnauthorizedError("Invalid API Key")

        transactions = self._transactions.list_by_agent(agent_id)
        total_earned = sum(tx.amount for tx in transactions if tx.amount > 0)
        total_spent = abs(sum(tx.amount for tx in transactions if tx.amount < 0))

        return {
            "agent_id": str(agent.agent_id),
            "token_balance": agent.token_balance,
            "total_earned": total_earned,
            "total_spent": total_spent,
            "recent_transactions": [
                self._serialize_transaction(tx) for tx in transactions[:10]
            ],
        }

    def search(self, query: str, limit: int, error_log: str | None = None) -> dict:
        rows = self._search_problems(query=query, limit=limit, error_log=error_log)
        return {"results": rows, "total": len(rows)}

    def _search_problems(self, query: str, limit: int, error_log: str | None = None) -> list[dict]:
        search_text = self._compose_search_text(query=query, error_log=error_log)
        normalized_query = search_text.lower()
        query_embedding = self._safe_embed(search_text)
        rows: list[dict] = []

        if query_embedding is not None:
            semantic_rows = self._problems.search_similar(query_embedding)
            for problem, similarity in semantic_rows:
                if problem.review_status != "approved":
                    continue
                best_solution = self._pick_best_solution(problem.problem_id)
                rows.append({
                    "problem_id": str(problem.problem_id),
                    "description": problem.description,
                    "best_confidence": problem.best_confidence,
                    "solution_count": problem.solution_count,
                    "similarity_score": similarity,
                    "best_solution": best_solution,
                    "created_at": problem.created_at.isoformat(),
                })

        if not rows:
            query_terms = self._extract_terms(normalized_query)
            for problem in self._problems.list_all():
                if problem.review_status != "approved":
                    continue
                desc_lower = problem.description.lower()
                matched = any(term in desc_lower for term in query_terms) if query_terms else True
                if normalized_query and not matched:
                    continue
                best_solution = self._pick_best_solution(problem.problem_id)
                rows.append({
                    "problem_id": str(problem.problem_id),
                    "description": problem.description,
                    "best_confidence": problem.best_confidence,
                    "solution_count": problem.solution_count,
                    "similarity_score": 1.0 if matched else 0.0,
                    "best_solution": best_solution,
                    "created_at": problem.created_at.isoformat(),
                })

        rows.sort(key=lambda item: item["similarity_score"], reverse=True)
        return rows[: max(limit, 0)]

    def _ensure_agent_exists(self, agent_id: UUID) -> None:
        if self._agents.get(agent_id) is None:
            raise UnauthorizedError("Invalid API Key")

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

    def _serialize_transaction(self, transaction: TokenTransaction) -> dict:
        row = asdict(transaction)
        row["tx_id"] = str(transaction.tx_id)
        row["agent_id"] = str(transaction.agent_id)
        row["related_solution_id"] = (
            None
            if transaction.related_solution_id is None
            else str(transaction.related_solution_id)
        )
        row["created_at"] = transaction.created_at.isoformat()
        return row

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
                self._transactions.clear_related_solution(sol.solution_id)
                self._solutions.delete(sol.solution_id)
            self._problems.delete(content_id)
            return
        s = self._solutions.get(content_id)
        if s is not None:
            self._transactions.clear_related_solution(content_id)
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
        return self._problems.find_unreviewed(limit=limit, retry_error_before=retry_error_before)

    def get_unreviewed_solutions(
        self,
        limit: int = 100,
        retry_error_before: datetime | None = None,
    ) -> list[Solution]:
        return self._solutions.find_unreviewed(limit=limit, retry_error_before=retry_error_before)

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
                result.append({
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
                })
            elif include_pending and viewer_id is not None and p.author_id == viewer_id:
                result.append({
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
                })
        return result[offset : offset + limit]

    def get_agentbook(self, problem_id: UUID) -> dict:
        problem = self._problems.get(problem_id)
        if problem is None:
            raise NotFoundError(f"Problem {problem_id} not found")

        all_solutions = self._solutions.list_by_problem(problem_id)
        # Exclude candidates from public view; show only validated (promoted/legacy) solutions
        visible_solutions = [
            s for s in all_solutions
            if s.review_status == "approved" and s.promotion_status != "candidate"
        ]

        canonical = None
        if problem.canonical_solution_id:
            canonical_sol = self._solutions.get(problem.canonical_solution_id)
            if canonical_sol:
                canonical = {
                    "solution_id": str(canonical_sol.solution_id),
                    "content": canonical_sol.content,
                    "steps": canonical_sol.steps,
                    "confidence": canonical_sol.confidence,
                    "outcome_count": canonical_sol.outcome_count,
                    "success_count": canonical_sol.success_count,
                    "author_id": str(canonical_sol.author_id),
                    "parent_solution_id": str(canonical_sol.parent_solution_id) if canonical_sol.parent_solution_id else None,
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
                "parent_solution_id": str(s.parent_solution_id) if s.parent_solution_id else None,
                "environment_scores": s.environment_scores,
                "created_at": s.created_at.isoformat(),
                "review_status": s.review_status,
            }
            for s in visible_solutions
            if problem.canonical_solution_id is None or s.solution_id != problem.canonical_solution_id
        ]

        return {
            "problem_id": str(problem.problem_id),
            "description": problem.description,
            "tags": problem.tags,
            "error_signature": problem.error_signature,
            "environment": problem.environment,
            "created_at": problem.created_at.isoformat(),
            "canonical_solution": canonical,
            "solution_history": history,
            "best_confidence": problem.best_confidence,
            "solution_count": problem.solution_count,
            "has_canonical": problem.canonical_solution_id is not None,
        }

    def _pick_best_solution(self, problem_id: UUID) -> dict | None:
        solutions = self._solutions.list_by_problem(problem_id)
        approved = [s for s in solutions if s.review_status == "approved"]
        if not approved:
            return None
        best = max(approved, key=lambda s: s.confidence)
        return {
            "solution_id": str(best.solution_id),
            "confidence": best.confidence,
            "content_preview": best.content[:200],
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
                rate = sol.success_count / sol.outcome_count if sol.outcome_count > 0 else sol.confidence
                return 0.6 * rate + 0.4 * sol.confidence

            all_solutions.sort(key=_rank, reverse=True)
            return {
                "status": "resolved",
                "problem_id": matched_problems[0].problem_id,
                "solutions": [_solution_to_dict(s) for s in all_solutions],
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
            return {"status": "registered", "problem_id": new_problem.problem_id, "solutions": []}

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
                "status": "solution_added" if solution_id is not None else "problem_created",
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

        # Candidate promotion/demotion: validate improvement against parent before superseding
        if solution.promotion_status == "candidate" and solution.parent_solution_id is not None:
            parent = self._solutions.get(solution.parent_solution_id)
            if parent is not None:
                ext_reporters = {o.reporter_id for o in all_outcomes if o.reporter_id != solution.author_id}
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

        reward_issued = False
        if success and reporter_id != solution.author_id:
            author = self._agents.get(solution.author_id)
            if author is not None:
                reward_amount = settings.reward_per_successful_outcome
                author.token_balance += reward_amount
                self._agents.add(author)
                self._transactions.add(TokenTransaction(
                    agent_id=author.agent_id,
                    amount=reward_amount,
                    tx_type="outcome_reward",
                    related_solution_id=solution.solution_id,
                    description="Received successful outcome report",
                ))
                reward_issued = True

        return {
            "status": "reported",
            "outcome_id": outcome.outcome_id,
            "solution_confidence_updated": new_confidence,
            "reward_issued": reward_issued,
        }

    def get_context(
        self,
        id: UUID,
        include: list[str] | None = None,
    ) -> dict:
        problem = self._problems.get(id)
        if problem is not None:
            effective = include if include is not None else ["solutions", "similar"]
            result: dict = {"type": "problem", "data": _problem_to_dict(problem)}
            if "solutions" in effective:
                sols = self._solutions.list_by_problem(problem.problem_id)
                result["solutions"] = [_solution_to_dict(s) for s in sols]
            if "similar" in effective and problem.embedding:
                similar = self._problems.find_similar(problem.embedding, threshold=0.6)
                result["similar"] = [
                    _problem_to_dict(p) for p in similar
                    if p.problem_id != problem.problem_id
                ]
            return result

        solution = self._solutions.get(id)
        if solution is not None:
            effective = include if include is not None else ["outcomes"]
            result = {"type": "solution", "data": _solution_to_dict(solution)}
            if "outcomes" in effective:
                outs = self._outcomes.list_by_solution(solution.solution_id)
                result["outcomes"] = [_outcome_to_dict(o) for o in outs]
            return result

        raise NotFoundError(f"No problem or solution found with id {id}")

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
                trending.append({
                    "problem_id": p.problem_id,
                    "description": p.description,
                    "agent_count": 1,
                    "solution_count": p.solution_count,
                    "resolution_rate": rate,
                    "last_24h_resolve_calls": recent_count,
                })
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

        return {"trending": trending, "new_unsolved": new_unsolved, "degrading": degrading}

    def get_metrics(self) -> dict:
        all_problems = self._problems.list_all()
        total_problems = len(all_problems)

        solved = sum(1 for p in all_problems if p.solution_count > 0)
        resolution_rate = round(solved / total_problems, 2) if total_problems > 0 else 0.0

        all_solutions = []
        for p in all_problems:
            all_solutions.extend(self._solutions.list_by_problem(p.problem_id))
        avg_confidence = round(
            sum(s.confidence for s in all_solutions) / len(all_solutions), 2
        ) if all_solutions else 0.0

        all_outcomes = []
        for sol in all_solutions:
            all_outcomes.extend(self._outcomes.list_by_solution(sol.solution_id))
        timed = [o.time_saved_seconds for o in all_outcomes if o.time_saved_seconds]
        median_ttr = int(sum(timed) / len(timed)) if timed else 0

        needs_synthesis = sum(
            1 for s in all_solutions
            if s.outcome_count >= 10 and s.confidence < 0.3
        )

        stale = sum(1 for s in all_solutions if s.outcome_count == 0)

        return {
            "resolution_rate": {"value": resolution_rate, "trend": None, "target": 0.80},
            "median_ttr_seconds": {"value": median_ttr, "trend": None, "target": 300},
            "avg_solution_confidence": {"value": avg_confidence, "trend": None, "target": 0.75},
            "knowledge_coverage": {"value": total_problems, "trend": None},
            "knowledge_freshness": {"value": round(resolution_rate * 0.9, 2), "trend": None, "target": 0.60},
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
                raise ValueError(f"Cycle detected in parent lineage")
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
        max_retries: int = 3,
    ) -> dict:
        """Wrapper with retry logic for concurrent modification handling."""
        for attempt in range(max_retries):
            try:
                return self._improve_solution_impl(
                    author_id, solution_id, improved_content, improved_steps, reasoning
                )
            except ConcurrentModificationError as e:
                if attempt == max_retries - 1:
                    raise
                # Exponential backoff with jitter: prevents thundering herd
                base_delay = 0.1 * (2 ** attempt)
                jitter = random.uniform(0, 0.05)  # 0-50ms random jitter
                delay = base_delay + jitter
                logger.warning(f"Concurrent modification detected, retrying in {delay:.3f}s: {e}")
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
    ) -> dict:
        """Public API with retry logic."""
        from uuid import UUID as _UUID
        _author_id = author_id or _UUID("00000000-0000-0000-0000-000000000001")
        return self._improve_solution_with_retry(
            _author_id, solution_id, improved_content, improved_steps, reasoning
        )

    def _improve_solution_impl(
        self,
        author_id: UUID,
        solution_id: UUID,
        improved_content: str,
        improved_steps: list[str] | None = None,
        reasoning: str = "",
    ) -> dict:
        existing = self._solutions.get(solution_id)
        if existing is None:
            raise NotFoundError(f"Solution {solution_id} not found")

        gate_result = check_spam(improved_content, "solution", {"steps": improved_steps} if improved_steps else None)
        ok = gate_result.passed
        # Check content regression before quality gate — too-short content is a regression, not an error
        new_step_count = len(improved_steps or [])
        existing_step_count = len(existing.steps or [])
        content_regression_early = (
            len(improved_content) < len(existing.content) * 0.5
            and new_step_count <= existing_step_count
        )
        if not ok and not content_regression_early:
            raise ValueError("solution_quality_check_failed")

        problem = self._problems.get(existing.problem_id)
        if problem is None:
            raise NotFoundError(f"Problem {existing.problem_id} not found")

        # Validate no cycle in parent's ancestry (prevents cycles from concurrent modifications)
        self._validate_no_lineage_cycle(solution_id)

        new_solution = Solution(
            problem_id=existing.problem_id,
            author_id=author_id,
            content=improved_content,
            steps=improved_steps or [],
            parent_solution_id=solution_id,
        )
        self._solutions.add(new_solution)

        previous_best = problem.best_confidence
        new_confidence = new_solution.confidence

        # Quality proxy: reject if new content is significantly shorter without more steps.
        # This acts as a pre-filter against regressions before confidence-based hill-climbing.
        new_step_count = len(improved_steps or [])
        existing_step_count = len(existing.steps or [])
        content_regression = (
            len(improved_content) < len(existing.content) * 0.5
            and new_step_count <= existing_step_count
        )
        content_bloat = (
            len(improved_content) > len(existing.content) * 2.0
            and new_confidence <= existing.confidence + 0.05
        )

        if not content_regression and not content_bloat and new_confidence > existing.confidence:
            # Hill-climbing: new is strictly better — mark as candidate (deferred validation)
            # The old solution is NOT immediately superseded; promotion happens when real
            # outcome data confirms the improvement (see report_outcome promotion logic).
            new_solution.promotion_status = "candidate"
            self._solutions.update(new_solution)
            problem.solution_count += 1
            self._problems.update(problem)
            status = "improved"
        else:
            # New is worse, equal, or a content regression — mark new as superseded by existing
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
            )
            self._research_cycles.add(cycle)

        return {
            "status": status,
            "solution_id": new_solution.solution_id,
            "previous_confidence": existing.confidence,
            "previous_problem_best": previous_best,
            "new_confidence": new_confidence,
        }

    def synthesize_solutions(
        self,
        problem_id: UUID,
        synthesized_content: str | None = None,
        author_id: UUID | None = None,
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
                f"Solution {i+1}:\n{s.content}" for i, s in enumerate(active[:5])
            )

        gate_result = check_spam(synthesized_content, "solution")
        if not gate_result.passed:
            synthesized_content = active[0].content if active else "Synthesized solution"

        canonical = Solution(
            problem_id=problem_id,
            author_id=_author_id,
            content=synthesized_content,
            outcome_count=total_outcomes,
            success_count=total_successes,
            failure_count=total_failures,
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
        needs_filtering = (cooldown_hours > 0 or stall_threshold > 0) and self._research_cycles is not None
        if not needs_filtering:
            candidates = self._problems.find_research_candidates(limit=limit, max_confidence=max_confidence)
            return [_problem_to_dict(p) for p in candidates]
        cutoff = utc_now() - timedelta(hours=cooldown_hours) if cooldown_hours > 0 else None
        page_size = max(limit, 10)
        offset = 0
        filtered: list = []
        while len(filtered) < limit:
            batch = self._problems.find_research_candidates(limit=page_size, offset=offset, max_confidence=max_confidence)
            if not batch:
                break
            for p in batch:
                if cutoff is not None:
                    last = self._research_cycles.last_researched_at(p.problem_id)
                    if last is not None and last >= cutoff:
                        continue
                if stall_threshold > 0:
                    stalled = self._research_cycles.consecutive_no_improvement(p.problem_id)
                    if stalled >= stall_threshold:
                        continue
                filtered.append(p)
                if len(filtered) >= limit:
                    break
            offset += page_size
        return [_problem_to_dict(p) for p in filtered]

    def record_research_skip(
        self,
        problem_id: UUID,
        researcher_id: UUID,
        reasoning: str = "",
        status: str = "no_improvement",
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
        )
        self._research_cycles.add(cycle)

    def get_solution_lineage(self, solution_id: UUID) -> list[dict]:
        solution = self._solutions.get(solution_id)
        if solution is None:
            raise NotFoundError(f"Solution {solution_id} not found")

        chain: list[Solution] = [solution]
        visited: set[UUID] = {solution_id}
        current = solution
        while current.parent_solution_id is not None and current.parent_solution_id not in visited:
            parent = self._solutions.get(current.parent_solution_id)
            if parent is None:
                break
            visited.add(parent.solution_id)
            chain.append(parent)
            current = parent

        chain.reverse()
        return [_solution_to_dict(s) for s in chain]

    def get_research_history(self, problem_id: UUID) -> list[dict]:
        if self._research_cycles is None:
            return []
        cycles = self._research_cycles.list_by_problem(problem_id)
        return [_research_cycle_to_dict(c) for c in cycles]

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

        events: list[dict] = []

        # Event: problem_created
        events.append({
            "event_type": "problem_created",
            "created_at": problem.created_at.isoformat(),
            "author_id": str(problem.author_id),
            "description": problem.description,
            "tags": problem.tags,
            "error_signature": problem.error_signature,
        })

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
                "parent_solution_id": str(s.parent_solution_id) if s.parent_solution_id else None,
                "outcome_count": s.outcome_count,
                "success_count": s.success_count,
                "failure_count": s.failure_count,
                "environment_scores": s.environment_scores,
                "review_status": s.review_status,
            }

            cycle = cycle_by_solution.get(s.solution_id)
            if cycle:
                entry["reasoning"] = cycle.reasoning
                entry["confidence_delta"] = round(cycle.new_confidence - cycle.previous_best_confidence, 4)
                entry["previous_best_confidence"] = cycle.previous_best_confidence
                entry["research_status"] = cycle.status

            events.append(entry)

        # Events: research_skipped (cycles without a proposed solution)
        for c in research_cycles:
            if c.proposed_solution_id is None:
                events.append({
                    "event_type": "research_skipped",
                    "created_at": c.created_at.isoformat(),
                    "author_id": str(c.researcher_id),
                    "reasoning": c.reasoning,
                    "status": c.status,
                    "previous_best_confidence": c.previous_best_confidence,
                })

        # Events: outcome_reported
        for o in all_outcomes:
            events.append({
                "event_type": "outcome_reported",
                "created_at": o.created_at.isoformat(),
                "author_id": str(o.reporter_id),
                "solution_id": str(o.solution_id),
                "success": o.success,
                "environment": o.environment,
                "notes": o.notes,
                "time_saved_seconds": o.time_saved_seconds,
                "weight": o.weight,
            })

        events.sort(key=lambda e: e["created_at"])

        return {
            "problem": {
                "problem_id": str(problem.problem_id),
                "author_id": str(problem.author_id),
                "description": problem.description,
                "tags": problem.tags,
                "error_signature": problem.error_signature,
                "best_confidence": problem.best_confidence,
                "solution_count": problem.solution_count,
                "created_at": problem.created_at.isoformat(),
                "has_canonical": problem.canonical_solution_id is not None,
            },
            "timeline": events,
        }


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


def _solution_to_dict(s: Solution) -> dict:
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
    }


def _research_cycle_to_dict(c: ResearchCycle) -> dict:
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
    }


def _outcome_to_dict(o: Outcome) -> dict:
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
    }
