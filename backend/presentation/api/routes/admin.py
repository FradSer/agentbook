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
def trajectory_export(
    service: AgentbookService = Depends(get_service),
    format: str = "flat",
) -> Response:
    if format == "pairs":
        rows = service.export_distillation_pairs()
    else:
        rows = service.export_trajectory_ledger()
    body = "".join(
        json.dumps(row, default=str, ensure_ascii=False) + "\n" for row in rows
    )
    return Response(content=body, media_type="application/x-ndjson")
