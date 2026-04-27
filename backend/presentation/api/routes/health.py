from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends

from backend.application.service import SANDBOX_AGENT_ID, AgentbookService
from backend.presentation.api.deps import get_service

router = APIRouter(prefix="/v1/health-metrics", tags=["health"])


@router.get("")
def get_health_metrics(
    service: AgentbookService = Depends(get_service),
) -> dict:
    counters = dict(service._health_counters)
    sandbox_pass_rate_24h, verified_count_24h = _sandbox_pass_rate(service)
    return {
        "sandbox_pass_rate_24h": sandbox_pass_rate_24h,
        "verified_outcome_count_24h": verified_count_24h,
        "single_identity_cluster_count_24h": counters.get("single_identity_cluster", 0),
        "counters": counters,
        "generated_at": datetime.now(tz=UTC),
    }


def _sandbox_pass_rate(service: AgentbookService) -> tuple[float, int]:
    """Compute sandbox pass rate over the last 24h from verified outcomes."""
    repo = service._outcomes
    since = datetime.now(tz=UTC) - timedelta(hours=24)
    outcomes = [o for o in repo.list_by_reporter(SANDBOX_AGENT_ID) if o.created_at >= since]
    if not outcomes:
        return 0.0, 0
    passes = sum(1 for o in outcomes if o.success)
    return passes / len(outcomes), len(outcomes)
