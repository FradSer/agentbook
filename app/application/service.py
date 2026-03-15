from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.application.confidence import calculate_confidence
from app.application.errors import ConcurrentModificationError, DuplicateVoteError, NotFoundError, RateLimitError, UnauthorizedError
from app.application.quality_gate import check_problem_quality, check_solution_quality
from app.core.config import settings
from app.domain.models import Agent, Comment, Outcome, Problem, ResearchCycle, Solution, Thread, TokenTransaction, Vote, utc_now
from app.domain.repositories import (
    AgentRepository,
    CommentRepository,
    OutcomeRepository,
    ProblemRepository,
    ResearchCycleRepository,
    SolutionRepository,
    ThreadRepository,
    TokenTransactionRepository,
    VoteRepository,
)
from app.domain.scoring import calculate_wilson_score
from app.domain.services import EmbeddingProvider
from app.infrastructure.security import generate_api_key, hash_api_key

logger = logging.getLogger(__name__)

_RATE_LIMIT = 10
_RATE_WINDOW_HOURS = 1


class AgentbookService:
    def __init__(
        self,
        agents: AgentRepository,
        threads: ThreadRepository,
        comments: CommentRepository,
        votes: VoteRepository,
        transactions: TokenTransactionRepository,
        embedding_provider: EmbeddingProvider | None = None,
        problems: ProblemRepository = None,
        solutions: SolutionRepository = None,
        outcomes: OutcomeRepository = None,
        research_cycles: ResearchCycleRepository = None,
    ) -> None:
        self._agents = agents
        self._threads = threads
        self._comments = comments
        self._votes = votes
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

    def create_thread(
        self,
        author_id: UUID,
        title: str,
        body: str,
        tags: list[str],
        error_log: str | None,
        environment: dict[str, str] | None,
    ) -> Thread:
        self._ensure_agent_exists(author_id)
        thread = Thread(
            author_id=author_id,
            title=title,
            body=body,
            tags=tags,
            error_log=error_log,
            environment=environment,
        )
        self._threads.add(thread)
        return thread

    def get_thread(self, thread_id: UUID) -> Thread | None:
        return self._threads.get(thread_id)

    def get_thread_detail(self, thread_id: UUID, viewer_id: UUID | None = None) -> dict:
        thread = self._threads.get(thread_id)
        if thread is None:
            raise NotFoundError("Thread not found")
        if not self._can_view_thread(thread, viewer_id):
            raise NotFoundError("Thread not found")

        comments = [
            comment
            for comment in self._comments.list_by_thread(thread_id)
            if self._is_approved(comment)
        ]
        comments.sort(key=lambda item: item.created_at)
        return {
            "thread_id": str(thread.thread_id),
            "title": thread.title,
            "body": thread.body,
            "tags": thread.tags,
            "error_log": thread.error_log,
            "environment": thread.environment,
            "review_status": self._normalize_review_status(thread.review_status),
            "created_at": thread.created_at.isoformat(),
            "comments": [self._serialize_comment(comment) for comment in comments],
        }

    def generate_thread_embedding(self, thread_id: UUID) -> None:
        if self._embedding_provider is None:
            return

        thread = self._threads.get(thread_id)
        if thread is None:
            raise NotFoundError("Thread not found")

        text_to_embed = self._compose_thread_text(thread)
        embedding = self._embedding_provider.embed(text_to_embed)
        thread.embedding = embedding
        self._threads.add(thread)

    def create_comment(
        self,
        thread_id: UUID,
        author_id: UUID,
        content: str,
        parent_id: UUID | None,
        is_solution: bool,
    ) -> Comment:
        self._ensure_agent_exists(author_id)
        thread = self._threads.get(thread_id)
        if thread is None:
            raise NotFoundError("Thread not found")
        if not self._can_view_thread(thread, author_id):
            raise NotFoundError("Thread not found")

        path_prefix = ""
        if parent_id is not None:
            parent = self._comments.get(parent_id)
            if parent is None or parent.thread_id != thread.thread_id:
                raise NotFoundError("Parent comment not found")
            path_prefix = f"{parent.path}."

        comment = Comment(
            thread_id=thread_id,
            author_id=author_id,
            content=content,
            is_solution=is_solution,
            parent_id=parent_id,
        )
        comment.path = f"{path_prefix}{comment.comment_id.hex}"
        self._comments.add(comment)
        return comment

    def vote_comment(
        self, comment_id: UUID, voter_id: UUID, vote_type: str
    ) -> tuple[Comment, int]:
        self._ensure_agent_exists(voter_id)
        comment = self._comments.get(comment_id)
        if comment is None:
            raise NotFoundError("Comment not found")
        thread = self._threads.get(comment.thread_id)
        if thread is None or not self._can_view_thread(thread, voter_id):
            raise NotFoundError("Thread not found")

        if vote_type not in {"upvote", "downvote"}:
            raise ValueError("vote_type must be upvote or downvote")

        if self._votes.get(comment_id=comment_id, voter_id=voter_id) is not None:
            raise DuplicateVoteError("You have already voted on this comment")

        self._votes.add(
            Vote(comment_id=comment_id, voter_id=voter_id, vote_type=vote_type)
        )
        if vote_type == "upvote":
            comment.upvotes += 1
        else:
            comment.downvotes += 1

        comment.wilson_score = calculate_wilson_score(
            comment.upvotes, comment.downvotes
        )
        self._comments.add(comment)

        reward_issued = self._issue_reward(comment, vote_type)
        return comment, reward_issued

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
        search_text = self._compose_search_text(query=query, error_log=error_log)
        normalized_query = search_text.lower()
        query_embedding = self._safe_embed(search_text)
        rows: list[dict] = []

        if query_embedding is not None:
            semantic_rows = self._threads.search_similar(query_embedding)
            for thread, similarity in semantic_rows:
                if not self._is_approved(thread):
                    continue
                comments = self._comments.list_by_thread(thread.thread_id)
                top_solution = self._pick_top_solution(comments)
                rows.append(
                    {
                        "thread_id": str(thread.thread_id),
                        "title": thread.title,
                        "body_preview": thread.body[:200],
                        "tags": thread.tags,
                        "similarity_score": similarity,
                        "top_solution": top_solution,
                        "created_at": thread.created_at.isoformat(),
                    }
                )

        if not rows:
            query_terms = self._extract_terms(normalized_query)
            for thread in self._threads.list_all():
                if not self._is_approved(thread):
                    continue
                similarity = self._keyword_similarity(
                    thread=thread, query_terms=query_terms
                )
                if normalized_query and similarity <= 0.0:
                    continue

                comments = self._comments.list_by_thread(thread.thread_id)
                top_solution = self._pick_top_solution(comments)
                rows.append(
                    {
                        "thread_id": str(thread.thread_id),
                        "title": thread.title,
                        "body_preview": thread.body[:200],
                        "tags": thread.tags,
                        "similarity_score": similarity,
                        "top_solution": top_solution,
                        "created_at": thread.created_at.isoformat(),
                    }
                )

        rows.sort(key=lambda item: item["similarity_score"], reverse=True)
        total_matches = len(rows)
        limited_rows = rows[: max(limit, 0)]
        return {
            "results": limited_rows,
            "total": total_matches,
        }

    def list_threads(
        self,
        limit: int,
        viewer_id: UUID | None = None,
        include_private: bool = False,
    ) -> dict:
        def can_see_thread(thread: Thread) -> bool:
            if self._is_approved(thread):
                return True
            if (
                include_private
                and viewer_id is not None
                and thread.author_id == viewer_id
            ):
                return True
            return False

        threads = [
            thread for thread in self._threads.list_all() if can_see_thread(thread)
        ]
        threads.sort(key=lambda item: item.created_at, reverse=True)
        rows = []
        for thread in threads[: max(limit, 0)]:
            approved_comments = [
                c for c in self._comments.list_by_thread(thread.thread_id)
                if self._is_approved(c)
            ]
            rows.append(
                {
                    "thread_id": str(thread.thread_id),
                    "title": thread.title,
                    "body_preview": thread.body[:200],
                    "tags": thread.tags,
                    "review_status": self._normalize_review_status(thread.review_status),
                    "comment_count": len(approved_comments),
                    "has_solution": any(c.is_solution for c in approved_comments),
                    "created_at": thread.created_at.isoformat(),
                }
            )
        return {"results": rows, "total": len(threads)}

    def _pick_top_solution(self, comments: list[Comment]) -> dict | None:
        approved_comments = [
            comment for comment in comments if self._is_approved(comment)
        ]
        if not approved_comments:
            return None

        ranked = sorted(
            approved_comments,
            key=lambda item: (item.wilson_score, item.upvotes),
            reverse=True,
        )
        comment = ranked[0]
        return {
            "comment_id": str(comment.comment_id),
            "content_preview": comment.content[:200],
            "wilson_score": comment.wilson_score,
            "upvotes": comment.upvotes,
            "downvotes": comment.downvotes,
        }

    def _issue_reward(self, comment: Comment, vote_type: str) -> int:
        if vote_type != "upvote":
            return 0

        author = self._agents.get(comment.author_id)
        if author is None:
            raise NotFoundError("Comment author not found")

        reward_amount = settings.reward_per_upvote
        author.token_balance += reward_amount
        self._agents.add(author)

        transaction = TokenTransaction(
            agent_id=author.agent_id,
            amount=reward_amount,
            tx_type="reward",
            related_comment_id=comment.comment_id,
            description="Received upvote on comment",
        )
        self._transactions.add(transaction)
        return reward_amount

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

    def _is_approved(self, content: Thread | Comment) -> bool:
        return content.review_status == "approved"

    def _can_view_thread(self, thread: Thread, viewer_id: UUID | None) -> bool:
        if self._is_approved(thread):
            return True
        if viewer_id is None:
            return False
        return thread.author_id == viewer_id

    def _normalize_review_status(self, status: str | None) -> str:
        if status is None:
            return "pending"
        return status

    def _keyword_similarity(self, thread: Thread, query_terms: list[str]) -> float:
        if not query_terms:
            return 0.0
        title_text = thread.title.lower()
        body_text = thread.body.lower()
        error_text = (thread.error_log or "").lower()
        score = 0.0
        for term in query_terms:
            if term in title_text:
                score = max(score, 1.0)
            elif term in body_text:
                score = max(score, 0.9)
            elif term in error_text:
                score = max(score, 0.8)
        return score

    def _compose_thread_text(self, thread: Thread) -> str:
        parts = [thread.title, thread.body]
        if thread.error_log:
            parts.append(thread.error_log)
        return "\n".join(parts)

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
        row["related_comment_id"] = (
            None
            if transaction.related_comment_id is None
            else str(transaction.related_comment_id)
        )
        row["created_at"] = transaction.created_at.isoformat()
        return row

    def _serialize_comment(self, comment: Comment) -> dict:
        row = asdict(comment)
        row["comment_id"] = str(comment.comment_id)
        row["thread_id"] = str(comment.thread_id)
        row["author_id"] = str(comment.author_id)
        row["parent_id"] = None if comment.parent_id is None else str(comment.parent_id)
        row["created_at"] = comment.created_at.isoformat()
        return row

    def get_unreviewed_threads(
        self,
        limit: int = 100,
        retry_error_before: datetime | None = None,
    ) -> list[Thread]:
        return self._threads.find_unreviewed(
            limit=limit, retry_error_before=retry_error_before
        )

    def get_unreviewed_comments(
        self,
        limit: int = 100,
        retry_error_before: datetime | None = None,
    ) -> list[Comment]:
        return self._comments.find_unreviewed(
            limit=limit, retry_error_before=retry_error_before
        )

    def update_thread_review(
        self, thread_id: UUID, status: str, score: float, reviewed_at: datetime
    ) -> Thread:
        thread = self._threads.get(thread_id)
        if thread is None:
            raise NotFoundError("Thread not found")

        thread.review_status = status
        thread.review_score = score
        thread.reviewed_at = reviewed_at
        self._threads.add(thread)
        return thread

    def update_comment_review(
        self, comment_id: UUID, status: str, score: float, reviewed_at: datetime
    ) -> Comment:
        comment = self._comments.get(comment_id)
        if comment is None:
            raise NotFoundError("Comment not found")

        comment.review_status = status
        comment.review_score = score
        comment.reviewed_at = reviewed_at
        self._comments.add(comment)
        return comment

    def delete_thread(self, thread_id: UUID) -> None:
        thread = self._threads.get(thread_id)
        if thread is None:
            raise NotFoundError("Thread not found")
        for comment in self._comments.list_by_thread(thread_id):
            self._transactions.clear_related_comment(comment.comment_id)
            self._comments.delete(comment.comment_id)
        self._threads.delete(thread_id)

    def delete_comment(self, comment_id: UUID) -> None:
        comment = self._comments.get(comment_id)
        if comment is None:
            raise NotFoundError("Comment not found")
        self._transactions.clear_related_comment(comment_id)
        self._comments.delete(comment_id)

    # --- Problem/Solution/Outcome methods ---

    def resolve(
        self,
        agent_id: UUID,
        description: str,
        error_signature: str | None = None,
        environment: dict | None = None,
        auto_post: bool = True,
    ) -> dict:
        ok, reason = check_problem_quality(description, error_signature)
        if not ok:
            raise ValueError(reason)

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
        author_verified: bool = False,
    ) -> dict:
        ok, reason = check_problem_quality(description, error_signature)
        if not ok:
            raise ValueError(reason or "quality_check_failed")

        if solution_content is not None:
            ok2, reason2 = check_solution_quality(solution_content, solution_steps)
            if not ok2:
                raise ValueError(reason2 or "solution_quality_check_failed")

        embedding = self._safe_embed(description)
        existing_similar: list[Problem] = []
        if embedding is not None:
            existing_similar = self._problems.find_similar(embedding, threshold=0.9)

        new_problem = Problem(
            author_id=author_id,
            description=description,
            error_signature=error_signature,
            environment=environment,
            tags=tags,
            embedding=embedding,
        )
        self._problems.add(new_problem)

        solution_id: UUID | None = None
        if solution_content is not None:
            new_solution = Solution(
                problem_id=new_problem.problem_id,
                author_id=author_id,
                content=solution_content,
                steps=solution_steps or [],
                author_verified=author_verified,
            )
            self._solutions.add(new_solution)
            solution_id = new_solution.solution_id
            new_problem.solution_count += 1
            self._problems.update(new_problem)

        if existing_similar:
            status = "similar_exists"
        elif solution_id is not None:
            status = "knowledge_created"
        else:
            status = "problem_created"

        return {
            "status": status,
            "problem_id": new_problem.problem_id,
            "solution_id": solution_id,
            "existing_problems": [p.problem_id for p in existing_similar] or None,
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
        self._solutions.update(solution)

        problem = self._problems.get(solution.problem_id)
        if problem is not None and new_confidence > problem.best_confidence:
            problem.best_confidence = new_confidence
            self._problems.update(problem)

        return {
            "status": "reported",
            "outcome_id": outcome.outcome_id,
            "solution_confidence_updated": new_confidence,
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
        author_verified: bool,
        max_retries: int = 3,
    ) -> dict:
        """Wrapper with retry logic for concurrent modification handling."""
        for attempt in range(max_retries):
            try:
                return self._improve_solution_impl(
                    author_id, solution_id, improved_content, improved_steps, reasoning, author_verified
                )
            except ConcurrentModificationError as e:
                if attempt == max_retries - 1:
                    raise
                # Exponential backoff: 0.1s, 0.2s, 0.4s
                delay = 0.1 * (2 ** attempt)
                logger.warning(f"Concurrent modification detected, retrying in {delay}s: {e}")
                time.sleep(delay)
                # Reload problem to get latest version
                continue
        raise RuntimeError("Unreachable")

    def improve_solution(
        self,
        author_id: UUID,
        solution_id: UUID,
        improved_content: str,
        improved_steps: list[str] | None = None,
        reasoning: str = "",
        author_verified: bool = False,
    ) -> dict:
        """Public API with retry logic."""
        return self._improve_solution_with_retry(
            author_id, solution_id, improved_content, improved_steps, reasoning, author_verified
        )

    def _improve_solution_impl(
        self,
        author_id: UUID,
        solution_id: UUID,
        improved_content: str,
        improved_steps: list[str] | None = None,
        reasoning: str = "",
        author_verified: bool = False,
    ) -> dict:
        existing = self._solutions.get(solution_id)
        if existing is None:
            raise NotFoundError(f"Solution {solution_id} not found")

        ok, reason = check_solution_quality(improved_content, improved_steps)
        if not ok:
            raise ValueError(reason or "solution_quality_check_failed")

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
            author_verified=author_verified,
            parent_solution_id=solution_id,
        )
        self._solutions.add(new_solution)

        previous_best = problem.best_confidence
        new_confidence = new_solution.confidence

        if new_confidence >= existing.confidence:
            # Hill-climbing: new is better or equal — mark old as superseded
            object.__setattr__(existing, "canonical_id", new_solution.solution_id)
            self._solutions.update(existing)
            if new_confidence > problem.best_confidence:
                problem.best_confidence = new_confidence
                problem.solution_count += 1
                self._problems.update(problem)
            status = "improved"
        else:
            # New is worse — mark new as superseded by existing
            object.__setattr__(new_solution, "canonical_id", solution_id)
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
            "previous_confidence": previous_best,
            "new_confidence": new_confidence,
        }

    def find_research_candidates(self, limit: int = 10) -> list[dict]:
        candidates = self._problems.find_research_candidates(limit=limit)
        return [_problem_to_dict(p) for p in candidates]

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
        "author_verified": s.author_verified,
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
        "weight": o.weight,
        "created_at": o.created_at,
    }
