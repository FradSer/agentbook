from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request

from backend.application.service import SANDBOX_AGENT_ID, AgentbookService
from backend.core.rate_limit import dynamic_search_limit, limiter
from backend.presentation.api.deps import get_service

router = APIRouter(prefix="/v1/health-metrics", tags=["health"])


@router.get("")
@limiter.limit(dynamic_search_limit)
def get_health_metrics(
    request: Request,
    service: AgentbookService = Depends(get_service),
) -> dict:
    counters = service.get_health_counters()
    sandbox_pass_rate_24h, verified_count_24h = _sandbox_pass_rate(service)
    # Surfaces the Railway pgvector-outage failure mode that otherwise
    # only manifests as silently degraded search quality.
    backend, pgvector_available = service.get_retrieval_status()
    return {
        "sandbox_pass_rate_24h": sandbox_pass_rate_24h,
        "verified_outcome_count_24h": verified_count_24h,
        "single_identity_cluster_count_24h": counters.get("single_identity_cluster", 0),
        "counters": counters,
        "search_backend": backend,
        "pgvector_available": pgvector_available,
        "embedding_provider": service.embedding_provider_name,
        "rerank_provider": service.rerank_provider_name,
        "generated_at": datetime.now(tz=UTC),
    }


def _sandbox_pass_rate(service: AgentbookService) -> tuple[float, int]:
    """Compute sandbox pass rate over the last 24h from verified outcomes."""
    since = datetime.now(tz=UTC) - timedelta(hours=24)
    outcomes = service.list_outcomes_by_reporter(SANDBOX_AGENT_ID, since=since)
    if not outcomes:
        return 0.0, 0
    passes = sum(1 for o in outcomes if o.success)
    return passes / len(outcomes), len(outcomes)
