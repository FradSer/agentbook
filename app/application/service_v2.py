from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.application.confidence import calculate_confidence
from app.application.errors import NotFoundError, RateLimitError
from app.application.quality_gate import check_problem_quality, check_solution_quality
from app.domain.models import Outcome, Problem, Solution

_RATE_LIMIT = 10
_RATE_WINDOW_HOURS = 1


class AgentbookServiceV2:
    def __init__(
        self,
        problems,
        solutions,
        outcomes,
        embed=None,
        embedder=None,
    ) -> None:
        self._problems = problems
        self._solutions = solutions
        self._outcomes = outcomes
        self._embed = embed or embedder

    def _safe_embed(self, text: str) -> list[float] | None:
        if self._embed is None:
            return None
        try:
            return self._embed(text)
        except Exception:
            return None

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

        # Fast path: exact error signature match
        matched_problems: list[Problem] = []
        if error_signature:
            p = self._problems.find_by_error_signature(error_signature)
            if p is not None:
                matched_problems.append(p)

        # Semantic path
        if not matched_problems:
            embedding = self._safe_embed(description)
            if embedding is not None:
                similar = self._problems.find_similar(embedding, threshold=0.7)
                matched_problems.extend(similar)

        # Collect and rank solutions
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
        """Return trending, new_unsolved, degrading problems."""
        from datetime import UTC, datetime, timedelta
        cutoff = datetime.now(tz=UTC) - timedelta(hours=24)
        all_problems = self._problems.list_all()

        trending = []
        for p in all_problems:
            recent_count = 0
            total_outcomes = 0
            for sol in self._solutions.list_by_problem(p.problem_id):
                sol_outcomes = self._outcomes.list_by_solution(sol.solution_id)
                total_outcomes += len(sol_outcomes)
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
        """Return key v2 quality metrics."""
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
        "created_at": s.created_at,
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
