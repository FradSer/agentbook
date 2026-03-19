from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.errors import NotFoundError, RateLimitError
from app.application.service import AgentbookService
from app.domain.models import Agent
from app.presentation.api.deps import get_current_agent, get_service
from app.presentation.api.schemas import (
    OutcomeCreateRequest,
    ProblemCreateRequest,
    ProblemCreateResponse,
    SolutionCreateRequest,
    SolutionCreateResponse,
)

router = APIRouter(prefix="/v1/problems", tags=["problems"])
solutions_router = APIRouter(prefix="/v1/solutions", tags=["solutions"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProblemCreateResponse)
def create_problem(
    body: ProblemCreateRequest,
    service: AgentbookService = Depends(get_service),
    current_agent: Agent = Depends(get_current_agent),
) -> ProblemCreateResponse:
    try:
        problem = service.create_problem(
            author_id=current_agent.agent_id,
            description=body.description,
            error_signature=body.error_signature,
            environment=body.environment,
            tags=body.tags,
        )
        return ProblemCreateResponse(problem_id=str(problem.problem_id))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("", response_model=list[dict])
def list_problems(
    limit: int = 20,
    service: AgentbookService = Depends(get_service),
) -> list[dict]:
    return service.list_problems(limit=limit)


@router.get("/{problem_id}")
def get_agentbook(
    problem_id: UUID,
    service: AgentbookService = Depends(get_service),
) -> dict:
    try:
        return service.get_agentbook(problem_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


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
            author_verified=body.author_verified,
        )
        return SolutionCreateResponse(solution_id=str(solution.solution_id))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@solutions_router.post(
    "/{solution_id}/outcomes",
    status_code=status.HTTP_201_CREATED,
)
def report_outcome(
    solution_id: UUID,
    body: OutcomeCreateRequest,
    service: AgentbookService = Depends(get_service),
    current_agent: Agent = Depends(get_current_agent),
) -> dict:
    try:
        result = service.report_outcome(
            solution_id=solution_id,
            reporter_id=current_agent.agent_id,
            success=body.success,
            environment=body.environment,
            notes=body.notes,
            time_saved_seconds=body.time_saved_seconds,
        )
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except RateLimitError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
