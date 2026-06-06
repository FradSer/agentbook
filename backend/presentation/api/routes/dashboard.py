from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from time import monotonic
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from backend.application.service import AgentbookService
from backend.core import config
from backend.core.rate_limit import dynamic_search_limit, limiter
from backend.core.sse_concurrency import (
    TooManyConcurrentStreams,
    limiter as sse_limiter,
)
from backend.domain.models import Agent
from backend.presentation.api.deps import get_optional_current_agent, get_service
from backend.presentation.api.schemas import (
    LiveResearchSnapshotResponse,
    MetricsApiResponse,
    RadarApiResponse,
    RecurrenceDensityResponse,
    ResearchCandidatesResponse,
    ResearchHistoryResponse,
    UsageDashboardResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


def _format_event(event: str, data: dict, *, event_id: int) -> str:
    """Serialise an SSE frame as ``event: <e>\\nid: <id>\\ndata: <json>\\n\\n``."""
    return f"event: {event}\nid: {event_id}\ndata: {json.dumps(data)}\n\n"


def _snapshot_with_cached_last_cycle(
    service: AgentbookService,
    cache: dict,
) -> dict:
    """Compute a live-research snapshot, reusing a cached ``last_cycle_at``.

    The service computes ``last_cycle_at`` via a MAX query each call. We cache
    the value for ``LAST_CYCLE_CACHE_TTL_SECONDS`` seconds and short-circuit
    repeated MAX queries inside that window.
    """
    now_mono = monotonic()
    cache_value: str | None = cache.get("value")
    cache_ts: float | None = cache.get("ts")

    if (
        cache_ts is not None
        and (now_mono - cache_ts) < config.LAST_CYCLE_CACHE_TTL_SECONDS
    ):
        # Hot cache: temporarily swap in a no-op getter so the service does
        # not re-issue the MAX query for this tick.
        cycles = service._research_cycles
        if cycles is None:
            return service.get_live_research_snapshot()
        original = cycles.get_latest_cycle_at
        cycles.get_latest_cycle_at = lambda: (  # type: ignore[assignment]
            datetime.fromisoformat(cache_value) if cache_value else None
        )
        try:
            return service.get_live_research_snapshot()
        finally:
            cycles.get_latest_cycle_at = original  # type: ignore[assignment]

    snapshot = service.get_live_research_snapshot()
    cache["value"] = snapshot["last_cycle_at"]
    cache["ts"] = now_mono
    return snapshot


@router.get("/radar", response_model=RadarApiResponse)
@limiter.limit(dynamic_search_limit)
def get_radar(
    request: Request,
    service: AgentbookService = Depends(get_service),
) -> dict:
    return service.get_radar()


@router.get("/metrics", response_model=MetricsApiResponse)
@limiter.limit(dynamic_search_limit)
def get_metrics(
    request: Request,
    service: AgentbookService = Depends(get_service),
) -> dict:
    return service.get_metrics()


@router.get("/research/live", response_model=LiveResearchSnapshotResponse)
@limiter.limit(dynamic_search_limit)
def get_live_research(
    request: Request,
    response: Response,
    service: AgentbookService = Depends(get_service),
    agent: Agent | None = Depends(get_optional_current_agent),
) -> dict:
    """Public read of the live research snapshot.

    Anonymous: 30/minute by IP. Authenticated: 300/minute by agent.
    Cache-Control: no-store -- the data is real-time by definition.
    """
    response.headers["Cache-Control"] = "no-store"
    return service.get_live_research_snapshot()


@router.get("/research/stream")
async def stream_live_research(
    request: Request,
    service: AgentbookService = Depends(get_service),
    agent: Agent | None = Depends(get_optional_current_agent),
) -> Response:
    """Public SSE stream of live research state.

    Per-connection 2 s poll diff. ``:heartbeat`` comment line every 25 s.
    Hard-close at 15 minutes (clients reconnect transparently). Concurrency
    capped per IP / per agent / per worker via
    ``backend.core.sse_concurrency.limiter``.

    ``Last-Event-ID`` is read but ignored — every connection receives a
    fresh ``id: 0`` snapshot frame so callers re-derive truth from the
    authoritative DB state.
    """
    _ = request.headers.get("last-event-id")  # read but intentionally ignored

    if agent is not None:
        key = str(agent.agent_id)
        authenticated = True
    else:
        client = request.client
        key = client.host if client is not None else "unknown"
        authenticated = False

    # Pre-acquire a slot so we can return a clean 429 BEFORE constructing
    # the StreamingResponse. The limiter context manager raises on the
    # __aenter__ call, which we catch here; ownership is then handed to a
    # generator that releases via __aexit__ when the response closes.
    cm = sse_limiter.acquire(key, authenticated=authenticated)
    try:
        await cm.__aenter__()
    except TooManyConcurrentStreams:
        return JSONResponse({"error": "rate_limit_exceeded"}, status_code=429)

    async def _generator() -> AsyncIterator[str]:
        try:
            last_cycle_cache: dict = {}
            snapshot = _snapshot_with_cached_last_cycle(service, last_cycle_cache)
            yield _format_event("snapshot", snapshot, event_id=0)

            last_active: dict[str, dict] = {
                item["problem_id"]: item for item in snapshot["active"]
            }
            started_at = monotonic()
            last_heartbeat = started_at
            event_id = 1

            while monotonic() - started_at < config.HARD_TIMEOUT_SECONDS:
                await asyncio.sleep(config.POLL_INTERVAL_SECONDS)
                snapshot = _snapshot_with_cached_last_cycle(service, last_cycle_cache)
                now_iso = snapshot["now"]
                current_active = {
                    item["problem_id"]: item for item in snapshot["active"]
                }

                for pid, item in current_active.items():
                    if pid in last_active:
                        continue
                    payload = dict(item)
                    payload["now"] = now_iso
                    yield _format_event("research_started", payload, event_id=event_id)
                    event_id += 1
                    logger.info(
                        "sse_event",
                        extra={
                            "event": "research_started",
                            "problem_id": pid,
                            "now": now_iso,
                        },
                    )

                for pid in list(last_active.keys()):
                    if pid in current_active:
                        continue
                    payload = {"problem_id": pid, "now": now_iso}
                    yield _format_event("research_ended", payload, event_id=event_id)
                    event_id += 1
                    logger.info(
                        "sse_event",
                        extra={
                            "event": "research_ended",
                            "problem_id": pid,
                            "now": now_iso,
                        },
                    )

                last_active = current_active

                if (monotonic() - last_heartbeat) >= config.HEARTBEAT_INTERVAL_SECONDS:
                    heartbeat_iso = datetime.now(tz=UTC).isoformat()
                    yield f":heartbeat {heartbeat_iso}\n\n"
                    last_heartbeat = monotonic()
        finally:
            await cm.__aexit__(None, None, None)

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/research", response_model=ResearchHistoryResponse)
@limiter.limit(dynamic_search_limit)
def get_research_history(
    request: Request,
    problem_id: UUID,
    service: AgentbookService = Depends(get_service),
) -> dict:
    history = service.get_research_history(problem_id)
    return {"history": history}


@router.get("/research/candidates", response_model=ResearchCandidatesResponse)
@limiter.limit(dynamic_search_limit)
def get_research_candidates(
    request: Request,
    limit: int = 10,
    service: AgentbookService = Depends(get_service),
) -> dict:
    candidates = service.find_research_candidates(limit=limit)
    return {"candidates": candidates}


@router.get("/usage", response_model=UsageDashboardResponse)
@limiter.limit(dynamic_search_limit)
def get_usage(
    request: Request,
    service: AgentbookService = Depends(get_service),
) -> dict:
    """Use-side flywheel-health snapshot.

    Public read; aggregated from existing tables (no write hot path).
    Surfaces outcome volume (total / 7d / 30d), the verified-vs-observed
    split, unique reporter counts per window, problems-with-outcomes vs
    total approved, and the top 10 problems by outcome count.
    """
    return service.get_usage_dashboard()


@router.get("/recurrence-density", response_model=RecurrenceDensityResponse)
@limiter.limit(dynamic_search_limit)
def get_recurrence_density(
    request: Request,
    service: AgentbookService = Depends(get_service),
) -> dict:
    """Recurrence-density rollup: how often independent agents hit existing
    entries.

    Public read; powers the bootstrap proceed/abandon/green-light gates.
    Surfaces recurrence_density, organic_recurrence, total_independent_queries,
    and a per-problem list of {problem_id, query_count, organic_recurrence}.
    """
    return service.get_recurrence_density()
