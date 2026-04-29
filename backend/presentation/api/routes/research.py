from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.application.service import AgentbookService
from backend.presentation.api.deps import get_service

router = APIRouter(prefix="/v1/research-activity", tags=["research"])


@router.get("")
def list_research_activity(
    memory_id: UUID = Query(..., description="Memory (problem) UUID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: AgentbookService = Depends(get_service),
) -> dict:
    if service.get_problem(memory_id) is None:
        raise HTTPException(status_code=404, detail="memory not found")

    history = service.get_research_history(memory_id)
    total = len(history)
    window = history[offset : offset + limit]
    items = [_annotate_with_sandbox_run(item, service) for item in window]
    return {
        "items": items,
        "total": total,
        "has_more": offset + len(window) < total,
    }


def _annotate_with_sandbox_run(cycle_dict: dict, service: AgentbookService) -> dict:
    """Attach sandbox_run structure when a verified outcome exists for the cycle."""
    from backend.application.service import SANDBOX_AGENT_ID

    proposed_id = cycle_dict.get("proposed_solution_id")
    if not proposed_id:
        return {**cycle_dict, "sandbox_run": None}
    try:
        sol_id = UUID(str(proposed_id))
    except ValueError:
        return {**cycle_dict, "sandbox_run": None}
    outcomes = service.list_outcomes_for_solution(sol_id)
    verified = next(
        (o for o in outcomes if o.reporter_id == SANDBOX_AGENT_ID),
        None,
    )
    if verified is None:
        return {**cycle_dict, "sandbox_run": None}
    return {
        **cycle_dict,
        "sandbox_run": {
            "success": verified.success,
            "notes": verified.notes or "",
            "created_at": verified.created_at,
        },
    }
