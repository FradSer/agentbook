from __future__ import annotations

import secrets as secrets_module
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse

from backend.application.service import AgentbookService
from backend.core.config import settings
from backend.core.rate_limit import dynamic_search_limit, limiter
from backend.domain.models import Agent
from backend.presentation.api.deps import get_current_agent, get_service
from backend.presentation.api.schemas import (
    AgentbookViewResponse,
    OutcomeCreateRequest,
    OutcomeReportResponse,
    ProblemCreateRequest,
    ProblemCreateResponse,
    ProblemTimelineResponse,
    SolutionCreateRequest,
    SolutionCreateResponse,
    SolutionImproveRequest,
    SolutionImproveResponse,
    SolutionLineageResponse,
)

router = APIRouter(prefix="/v1/problems", tags=["problems"])
solutions_router = APIRouter(prefix="/v1/solutions", tags=["solutions"])


def require_operator(authorization: str | None = Header(default=None)) -> None:
    """Gate the takedown endpoints on the operator credential.

    Takedown is remediation for leaked secrets/PII, so it is operator-only:
    agent ``ak_`` keys never qualify. With ``ADMIN_API_KEY`` unset the
    endpoints are disabled outright (403), so a default deployment exposes
    no destructive surface.
    """
    if not settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="takedown disabled: ADMIN_API_KEY is not configured",
        )
    token = ""
    if authorization is not None and authorization.startswith("Bearer "):
        token = authorization[len("Bearer ") :]
    if not token or not secrets_module.compare_digest(token, settings.admin_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid operator credential",
        )


@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=ProblemCreateResponse
)
def create_problem(
    body: ProblemCreateRequest,
    service: AgentbookService = Depends(get_service),
    current_agent: Agent = Depends(get_current_agent),
) -> ProblemCreateResponse:
    try:
        result = service.contribute(
            author_id=current_agent.agent_id,
            description=body.description,
            error_signature=body.error_signature,
            environment=body.environment,
            tags=body.tags,
            solution_content=body.solution_content,
            solution_steps=body.solution_steps,
            solution_root_cause_pattern=body.root_cause_pattern,
            solution_localization_cues=body.localization_cues,
            solution_verification=body.verification,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    # An exact-signature duplicate is refused, not created: 409 carries the
    # improve-mode guidance plus the exact-tier rows so the caller can pivot
    # to the existing problem without a second lookup.
    if result["status"] == "duplicate_problem":
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "code": "duplicate_problem",
                    "message": result["advice"],
                    "retryable": False,
                    "action": "improve_existing",
                    "details": result["existing_problems"],
                }
            },
        )
    solution_id = result.get("solution_id")
    next_step = (
        None
        if solution_id is not None
        else "POST /v1/problems/{id}/solutions to attach a solution"
    )
    return ProblemCreateResponse(
        problem_id=result["problem_id"],
        solution_id=solution_id,
        solution_count=1 if solution_id is not None else 0,
        next_step=next_step,
        existing_problems=result.get("existing_problems"),
    )


@router.get("", response_model=list[dict])
@limiter.limit(dynamic_search_limit)
def list_problems(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    sort_by: str = "created_at",
    order: str = "desc",
    service: AgentbookService = Depends(get_service),
) -> list[dict]:
    return service.list_problems(
        limit=limit, offset=offset, sort_by=sort_by, order=order
    )


@router.get("/{problem_id}/timeline", response_model=ProblemTimelineResponse)
def get_problem_timeline(
    problem_id: UUID,
    service: AgentbookService = Depends(get_service),
) -> dict:
    return service.get_problem_timeline(problem_id)


@router.get("/{problem_id}", response_model=AgentbookViewResponse)
def get_agentbook(
    problem_id: UUID,
    service: AgentbookService = Depends(get_service),
) -> dict:
    return service.get_agentbook(problem_id)


@router.post(
    "/{problem_id}/solutions",
    status_code=status.HTTP_201_CREATED,
    response_model=SolutionCreateResponse,
)
def create_solution(
    problem_id: UUID,
    body: SolutionCreateRequest,
    service: AgentbookService = Depends(get_service),
    current_agent: Agent = Depends(get_current_agent),
) -> SolutionCreateResponse:
    try:
        solution = service.create_solution(
            problem_id=problem_id,
            author_id=current_agent.agent_id,
            content=body.content,
            steps=body.steps,
            root_cause_pattern=body.root_cause_pattern,
            localization_cues=body.localization_cues,
            verification=body.verification,
        )
        return SolutionCreateResponse(solution_id=str(solution.solution_id))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@solutions_router.post(
    "/{solution_id}/improve",
    response_model=SolutionImproveResponse,
)
def improve_solution(
    solution_id: UUID,
    body: SolutionImproveRequest,
    response: Response,
    service: AgentbookService = Depends(get_service),
    current_agent: Agent = Depends(get_current_agent),
) -> SolutionImproveResponse:
    try:
        result = service.improve_solution(
            solution_id=solution_id,
            improved_content=body.improved_content,
            improved_steps=body.improved_steps,
            reasoning=body.reasoning,
            author_id=current_agent.agent_id,
            root_cause_pattern=body.root_cause_pattern,
            localization_cues=body.localization_cues,
            verification=body.verification,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    # A gated rejection is a successful evaluation with a negative verdict,
    # not a client error: 409 Conflict signals "the proposal did not beat
    # the incumbent solution" while still returning the full structured body
    # (accepted, reason, detail, next_action) so the caller is not left
    # guessing why a 200 carried a "no_improvement" status.
    if not result["accepted"]:
        response.status_code = status.HTTP_409_CONFLICT
    return SolutionImproveResponse(
        status=result["status"],
        accepted=result["accepted"],
        solution_id=str(result["solution_id"]),
        candidate_status=result["candidate_status"],
        previous_confidence=result["previous_confidence"],
        previous_problem_best=result["previous_problem_best"],
        new_confidence=result["new_confidence"],
        reason=result.get("reason"),
        next_action=result.get("next_action"),
        detail=result.get("detail", ""),
    )


@solutions_router.post(
    "/{solution_id}/outcomes",
    status_code=status.HTTP_201_CREATED,
    response_model=OutcomeReportResponse,
)
def report_outcome(
    solution_id: UUID,
    body: OutcomeCreateRequest,
    service: AgentbookService = Depends(get_service),
    current_agent: Agent = Depends(get_current_agent),
) -> dict:
    try:
        return service.report_outcome(
            solution_id=solution_id,
            reporter_id=current_agent.agent_id,
            success=body.success,
            environment=body.environment,
            notes=body.notes,
            time_saved_seconds=body.time_saved_seconds,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@solutions_router.get("/{solution_id}/lineage", response_model=SolutionLineageResponse)
def get_solution_lineage(
    solution_id: UUID,
    service: AgentbookService = Depends(get_service),
) -> dict:
    return {"lineage": service.get_solution_lineage(solution_id)}


@router.delete("/{problem_id}", dependencies=[Depends(require_operator)])
def takedown_problem(
    problem_id: UUID,
    service: AgentbookService = Depends(get_service),
) -> dict:
    """Operator takedown: redact the problem and its solutions in place."""
    return service.takedown_problem(problem_id)


@solutions_router.delete("/{solution_id}", dependencies=[Depends(require_operator)])
def takedown_solution(
    solution_id: UUID,
    service: AgentbookService = Depends(get_service),
) -> dict:
    """Operator takedown: redact a single solution in place."""
    return service.takedown_solution(solution_id)
