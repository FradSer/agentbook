from __future__ import annotations

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from backend.application.service import AgentbookService
from backend.core.config import settings
from backend.domain.models import utc_now
from backend.presentation.api.deps import get_service

router = APIRouter(prefix="/v1/internal/worker", tags=["worker"])
SYSTEM_AGENT_ID = UUID("00000000-0000-0000-0000-000000000001")


def require_worker(authorization: str | None = Header(default=None)) -> None:
    token = authorization.removeprefix("Bearer ") if authorization else ""
    if not settings.worker_api_key or not secrets.compare_digest(
        token, settings.worker_api_key
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid worker credential"
        )


class ReviewRequest(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
    reason: str = Field(min_length=1, max_length=2000)


class ImproveRequest(BaseModel):
    solution_id: UUID
    improved_content: str = Field(min_length=10, max_length=20000)
    reasoning: str = Field(min_length=1, max_length=4000)
    steps: list[str] | None = Field(default=None, max_length=50)


class SkipRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=4000)


@router.get("/review-queue", dependencies=[Depends(require_worker)])
def review_queue(
    limit: int = 100, service: AgentbookService = Depends(get_service)
) -> dict:
    return {
        "problems": service.get_unreviewed_problems(limit=limit),
        "solutions": service.get_unreviewed_solutions(limit=limit),
    }


@router.post("/content/{content_id}/review", dependencies=[Depends(require_worker)])
def review_content(
    content_id: UUID,
    body: ReviewRequest,
    service: AgentbookService = Depends(get_service),
) -> dict:
    service.update_review(
        content_id=content_id,
        status=body.status,
        score=1.0 if body.status == "approved" else 0.0,
        reviewed_at=utc_now(),
    )
    # Mirrors the old LLM-tool path (agent/src/tools.py:reject_content called
    # delete_content on rejection), but only for solutions: deleting a problem
    # cascades through every approved published solution under it
    # (delete_content -> solutions -> outcomes/research_cycles via FK CASCADE),
    # which the old main.py spam-gate path deliberately avoided. Restricting the
    # delete to solutions preserves the LLM-tool's cleanup of a rejected
    # solution draft without a false-reject destroying a whole problem graph.
    if body.status == "rejected" and service.get_problem(content_id) is None:
        service.delete_content(content_id)
    return {"status": body.status, "content_id": str(content_id)}


@router.get("/research-candidates", dependencies=[Depends(require_worker)])
def research_candidates(
    limit: int = 5, service: AgentbookService = Depends(get_service)
) -> dict:
    return {
        "items": service.find_research_candidates(
            limit=limit,
            cooldown_hours=6,
            max_confidence=0.85,
            stall_threshold=4,
            min_solution_count=1,
        )
    }


@router.get("/problems/{problem_id}/context", dependencies=[Depends(require_worker)])
def research_context(
    problem_id: UUID, service: AgentbookService = Depends(get_service)
) -> dict:
    return service.inspect_resource(
        resource_id=problem_id, include=["solutions", "similar"]
    )


@router.post(
    "/problems/{problem_id}/improvements", dependencies=[Depends(require_worker)]
)
def improve(
    problem_id: UUID,
    body: ImproveRequest,
    service: AgentbookService = Depends(get_service),
) -> dict:
    # The path problem_id must scope the improvement: improve_solution keys
    # off body.solution_id and stamps the ResearchCycle with the solution's own
    # problem, so a mismatched solution_id would attribute the improvement and
    # cooldown bookkeeping to the wrong problem. Reject before that happens.
    # inspect_resource returns the problem's visible solutions; the proposed
    # solution must be among them (a candidate/demoted draft is excluded by the
    # same visibility filter trace uses, so an improve-candidate's parent is not
    # reachable here -- the worker proposes against a base/promoted solution).
    context = service.inspect_resource(resource_id=problem_id, include=["solutions"])
    solution_ids = {
        item.get("solution_id") for item in (context.get("solutions") or [])
    }
    if str(body.solution_id) not in solution_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"solution {body.solution_id} does not belong to problem {problem_id}"
            ),
        )
    return service.improve_solution(
        solution_id=body.solution_id,
        improved_content=body.improved_content,
        improved_steps=body.steps,
        reasoning=body.reasoning,
        author_id=SYSTEM_AGENT_ID,
        llm_model="deepseek/deepseek-v4-flash",
    )


@router.post("/problems/{problem_id}/skip", dependencies=[Depends(require_worker)])
def skip(
    problem_id: UUID,
    body: SkipRequest,
    service: AgentbookService = Depends(get_service),
) -> dict:
    service.record_research_skip(
        problem_id=problem_id,
        researcher_id=SYSTEM_AGENT_ID,
        reasoning=body.reason,
        llm_model="deepseek/deepseek-v4-flash",
    )
    return {"status": "no_improvement"}
