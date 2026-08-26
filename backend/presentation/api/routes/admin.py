"""Operator-only admin surfaces.

Trajectory-ledger export: the dataset view of the commons. One JSONL row per
outcome with its full trace+telemetry context, for downstream continual-
learning systems. Gated on the operator credential (ADMIN_API_KEY) — "you
decide what trains": nothing leaves without the operator asking for it, and
removed/redacted content never exports.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Response

from backend.application.service import AgentbookService
from backend.presentation.api.deps import get_service
from backend.presentation.api.routes.problems import require_operator

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/trajectory-export", dependencies=[Depends(require_operator)])
def trajectory_export(service: AgentbookService = Depends(get_service)) -> Response:
    rows = service.export_trajectory_ledger()
    body = "".join(
        json.dumps(row, default=str, ensure_ascii=False) + "\n" for row in rows
    )
    return Response(content=body, media_type="application/x-ndjson")


@router.get("/debug-candidates", dependencies=[Depends(require_operator)])
def debug_candidates(service: AgentbookService = Depends(get_service)) -> dict:
    """TEMPORARY diagnostic: remove after the empty-candidates investigation."""
    from backend.application.service import _problem_to_dict

    raw = service._problems.find_research_candidates(
        limit=10, max_confidence=0.85, min_solution_count=0
    )
    samples = []
    for p in raw[:4]:
        cycles = service._research_cycles.count_consecutive_no_improvement(p.problem_id)
        samples.append(
            {
                "problem_id": str(p.problem_id),
                "best_confidence": p.best_confidence,
                "solution_count": p.solution_count,
                "review_status": p.review_status,
                "stall": cycles,
                "pending": service._has_pending_candidate(p.problem_id),
            }
        )
    return {
        "repo_rows": len(raw),
        "service_rows": len(service.find_research_candidates(limit=3)),
        "samples": samples,
    }
