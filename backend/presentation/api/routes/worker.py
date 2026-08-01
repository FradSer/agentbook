from __future__ import annotations

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from backend.application.gate import (
    check_spam,
    detect_secret_in,
    secret_rejection,
)
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


def _gate_problem(
    description: str,
    error_signature: str | None,
    environment: object,
    tags: object,
):
    result = check_spam(description, "problem")
    struct_label = detect_secret_in(error_signature, environment, tags)
    return secret_rejection(struct_label) if struct_label and result.passed else result


def _gate_solution(
    content: str,
    steps: object,
    root_cause_pattern: object,
    localization_cues: object,
    verification: object,
):
    result = check_spam(content, "solution", {"steps": steps} if steps else None)
    struct_label = detect_secret_in(
        root_cause_pattern, localization_cues, verification
    )
    return secret_rejection(struct_label) if struct_label and result.passed else result


def _reject_gate_failure(
    service: AgentbookService, content_id: UUID
) -> None:
    service.update_review(
        content_id=content_id,
        status="rejected",
        score=0.0,
        reviewed_at=utc_now(),
    )


@router.get("/review-queue", dependencies=[Depends(require_worker)])
def review_queue(
    limit: int = 100, service: AgentbookService = Depends(get_service)
) -> dict:
    # Project to the fields the reviewer needs, not the raw domain dataclass.
    # Problem/Solution carry embedding (1024 floats on prod), version, and
    # review_score/reviewed_at; the worker tool JSON.stringifies the whole
    # body into the model's context, so unprojected responses push ~0.5-1MB
    # of vectors into every cycle under a 40-req/h gateway cap. The old
    # Python loop fed only {problem_id, description} (agent/src/main.py:81-92).
    problems = []
    for problem in service.get_unreviewed_problems(limit=limit):
        result = _gate_problem(
            problem.description,
            problem.error_signature,
            problem.environment,
            problem.tags,
        )
        if not result.passed:
            _reject_gate_failure(service, problem.problem_id)
            continue
        problems.append(
            {
                "problem_id": str(problem.problem_id),
                "description": problem.description,
                "error_signature": problem.error_signature,
                "environment": problem.environment,
                "tags": list(problem.tags or []),
                "review_status": problem.review_status,
                "created_at": problem.created_at,
            }
        )

    solutions = []
    for solution in service.get_unreviewed_solutions(limit=limit):
        result = _gate_solution(
            solution.content,
            solution.steps,
            solution.root_cause_pattern,
            solution.localization_cues,
            solution.verification,
        )
        if not result.passed:
            _reject_gate_failure(service, solution.solution_id)
            continue
        solutions.append(
            {
                "solution_id": str(solution.solution_id),
                "problem_id": str(solution.problem_id),
                "content": solution.content,
                "steps": list(solution.steps or []),
                "confidence": solution.confidence,
                "promotion_status": solution.promotion_status,
                "review_status": solution.review_status,
                "created_at": solution.created_at,
            }
        )
    return {"problems": problems, "solutions": solutions}


@router.post("/content/{content_id}/review", dependencies=[Depends(require_worker)])
def review_content(
    content_id: UUID,
    body: ReviewRequest,
    service: AgentbookService = Depends(get_service),
) -> dict:
    # Re-run the deterministic secret/spam gate before honoring the model's
    # verdict. The gated insert paths (create_problem/create_solution/improve)
    # already run check_spam at insert and stamp review_status="approved", so
    # the queue holds only legacy/error-retry rows that predate the gate; one of
    # those can embed a credential, and without this pre-gate deepseek-v4-flash
    # approving it would publish the secret on list_problems/get_agentbook
    # (both filter on review_status=="approved"). The old Python loop ran this
    # deterministically before the LLM saw the row; mirror that invariant here.
    problem = service.get_problem(content_id)
    if problem is not None and problem.review_status == "removed":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    if problem is not None:
        result = _gate_problem(
            problem.description,
            problem.error_signature,
            problem.environment,
            problem.tags,
        )
    else:
        # inspect_resource for a solution id returns {"type": "solution",
        # "data": <_solution_to_dict>}; the "data" dict carries the published
        # fields. The earlier code read solution.get("solutions") which only
        # exists on problem resources, so content was always "" and
        # check_spam("") forced every queued solution to be rejected before the
        # model's verdict. Pass steps as check_spam metadata (mirrors
        # create_solution) and scan root_cause_pattern / localization_cues /
        # verification via detect_secret_in — the structured-knowledge fields
        # emitted on every public read that bypass the content gate.
        solution = service.inspect_resource(
            resource_id=content_id, include=["outcomes"]
        )
        sdata = solution.get("data") or {}
        if isinstance(sdata, dict) and sdata.get("review_status") == "removed":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Content not found"
            )
        content = sdata.get("content", "") if isinstance(sdata, dict) else ""
        steps = sdata.get("steps") if isinstance(sdata, dict) else None
        result = _gate_solution(
            content,
            steps,
            sdata.get("root_cause_pattern") if isinstance(sdata, dict) else None,
            sdata.get("localization_cues") if isinstance(sdata, dict) else None,
            sdata.get("verification") if isinstance(sdata, dict) else None,
        )
    if not result.passed:
        _reject_gate_failure(service, content_id)
        return {
            "status": "rejected",
            "content_id": str(content_id),
            "reason": result.reason,
        }
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
    if body.status == "rejected" and problem is None:
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
    # inspect_resource serializes solution_id as a UUID object, so compare as
    # UUID — str(body.solution_id) against a set of UUIDs would always be False
    # and the route would 422 on every legitimate improvement.
    solution_ids = {
        item.get("solution_id") for item in (context.get("solutions") or [])
    }
    if body.solution_id not in solution_ids:
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
