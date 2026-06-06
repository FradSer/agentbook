"""SSE stream contract for GET /v1/dashboard/research/stream.

Per-connection 2 s poll-and-diff loop; emits an initial ``snapshot`` frame,
then ``research_started`` / ``research_ended`` events on state change, plus
``:heartbeat`` comment lines every 25 s. Concurrency capped by the limiter
in ``backend.core.sse_concurrency``. ``Last-Event-ID`` is read but ignored
(server always re-emits a fresh snapshot at id=0).

Tests use ``httpx.AsyncClient`` with ``ASGITransport``. ``ASGITransport``
buffers the entire response body before yielding it, so each test drives a
short-lived stream (the autouse ``HARD_TIMEOUT_SECONDS=2`` causes the
generator to terminate quickly) and then asserts on the accumulated SSE
buffer. State-change tests schedule a concurrent ``asyncio`` task that
mutates the in-memory repo while the generator is running.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from backend.application.service import AgentbookService
from backend.core.config import settings as app_settings
from backend.core.sse_concurrency import SSEConcurrencyLimiter
from backend.domain.models import Agent, Problem
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_sse_limiter():
    """Replace the module-level SSE limiter so per-key counts don't bleed."""
    from backend.core import sse_concurrency

    original = sse_concurrency.limiter
    sse_concurrency.limiter = SSEConcurrencyLimiter()
    try:
        yield
    finally:
        sse_concurrency.limiter = original


@pytest.fixture(autouse=True)
def _short_stream_timeouts(monkeypatch):
    """Default short SSE timing knobs so stream generators finish quickly.

    Without this, every test would block on cleanup waiting for the 15-min
    HARD_TIMEOUT generator loop to exit. Individual tests can override
    these constants for finer control.
    """
    monkeypatch.setattr("backend.core.config.POLL_INTERVAL_SECONDS", 0.05)
    monkeypatch.setattr("backend.core.config.HARD_TIMEOUT_SECONDS", 1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_service_and_app():
    """Build an AgentbookService + FastAPI app wired for in-memory repos."""
    from backend.main import create_app
    from backend.presentation.api.deps import get_service

    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(Agent(api_key_hash="test-hash", model_type="test", agent_id=author_id))
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return service, app, author_id


def _seed_active_problem(
    service: AgentbookService, author_id, *, started_offset_seconds: float = 30.0
) -> Problem:
    started_at = datetime.now(tz=UTC) - timedelta(seconds=started_offset_seconds)
    problem = Problem(
        author_id=author_id,
        description="Active research problem with sufficient description length.",
        review_status="approved",
        research_started_at=started_at,
        solution_count=2,
        best_confidence=0.7,
    )
    service._problems.add(problem)
    return problem


def _async_client(app) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def _parse_frames(text: str) -> list[dict]:
    """Parse an SSE buffer into a list of frame dicts.

    Each frame is ``{"event": str, "id": str|None, "data": str|None,
    "comment": str|None}``. Heartbeat comment lines emit a frame with
    ``comment`` populated and ``event`` left as ``"message"``.
    """
    frames: list[dict] = []
    for chunk in text.split("\n\n"):
        if not chunk.strip():
            continue
        frame = {"event": "message", "id": None, "data": None, "comment": None}
        for line in chunk.split("\n"):
            if line.startswith(":"):
                frame["comment"] = line[1:].lstrip()
            elif line.startswith("event:"):
                frame["event"] = line[len("event:") :].strip()
            elif line.startswith("id:"):
                frame["id"] = line[len("id:") :].strip()
            elif line.startswith("data:"):
                frame["data"] = line[len("data:") :].strip()
        frames.append(frame)
    return frames


async def _drain_response_body(response: httpx.Response) -> str:
    """Drain ``aiter_text`` to a single string. ASGITransport buffers the
    entire response, so this returns the full SSE log once the generator on
    the server side has terminated (HARD_TIMEOUT)."""
    chunks: list[str] = []
    async for chunk in response.aiter_text():
        chunks.append(chunk)
    return "".join(chunks)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_given_anonymous_client_when_subscribing_then_returns_200_and_event_stream_content_type():
    _, app, _ = _build_service_and_app()

    async with (
        _async_client(app) as client,
        client.stream("GET", "/v1/dashboard/research/stream") as response,
    ):
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")


@pytest.mark.asyncio
async def test_given_open_stream_when_reading_first_frame_then_it_is_event_snapshot_with_valid_json():
    _, app, _ = _build_service_and_app()

    async with (
        _async_client(app) as client,
        client.stream("GET", "/v1/dashboard/research/stream") as response,
    ):
        body = await _drain_response_body(response)

    frames = _parse_frames(body)
    assert frames, f"no frames received; body={body!r}"
    first = frames[0]
    assert first["event"] == "snapshot"
    assert first["id"] == "0"
    assert first["data"] is not None
    payload = json.loads(first["data"])
    assert "active" in payload
    assert "now" in payload


@pytest.mark.asyncio
async def test_given_research_started_when_polling_loop_runs_then_research_started_event_emitted():
    service, app, author_id = _build_service_and_app()

    state = {"problem_id": None}

    async def _seed_after_first_poll() -> None:
        # Wait for the initial snapshot + at least one poll tick.
        await asyncio.sleep(0.15)
        problem = _seed_active_problem(service, author_id)
        state["problem_id"] = str(problem.problem_id)

    async with _async_client(app) as client:
        seeder = asyncio.create_task(_seed_after_first_poll())
        async with client.stream("GET", "/v1/dashboard/research/stream") as response:
            body = await _drain_response_body(response)
        await seeder

    frames = _parse_frames(body)
    started_frames = [f for f in frames if f["event"] == "research_started"]
    assert started_frames, (
        f"expected research_started; events={[f['event'] for f in frames]}"
    )
    payload = json.loads(started_frames[0]["data"])
    assert payload["problem_id"] == state["problem_id"]


@pytest.mark.asyncio
async def test_given_research_clears_when_polling_loop_runs_then_research_ended_event_emitted():
    service, app, author_id = _build_service_and_app()
    problem = _seed_active_problem(service, author_id)

    async def _clear_after_first_poll() -> None:
        await asyncio.sleep(0.15)
        # Mutate the in-memory record directly to clear research_started_at;
        # bypass the optimistic-lock dance.
        record = service._problems.get(problem.problem_id)
        record.research_started_at = None

    async with _async_client(app) as client:
        clearer = asyncio.create_task(_clear_after_first_poll())
        async with client.stream("GET", "/v1/dashboard/research/stream") as response:
            body = await _drain_response_body(response)
        await clearer

    frames = _parse_frames(body)
    ended_frames = [f for f in frames if f["event"] == "research_ended"]
    assert ended_frames, (
        f"expected research_ended; events={[f['event'] for f in frames]}"
    )


@pytest.mark.asyncio
async def test_given_stale_row_falls_out_of_window_when_polling_then_research_ended_emitted():
    service, app, author_id = _build_service_and_app()
    # Seed a problem at 359s old (still inside the 360s window initially).
    problem = _seed_active_problem(service, author_id, started_offset_seconds=359.0)

    async def _push_past_window_after_first_poll() -> None:
        await asyncio.sleep(0.15)
        record = service._problems.get(problem.problem_id)
        record.research_started_at = datetime.now(tz=UTC) - timedelta(seconds=361)

    async with _async_client(app) as client:
        ager = asyncio.create_task(_push_past_window_after_first_poll())
        async with client.stream("GET", "/v1/dashboard/research/stream") as response:
            body = await _drain_response_body(response)
        await ager

    frames = _parse_frames(body)
    ended_frames = [f for f in frames if f["event"] == "research_ended"]
    assert ended_frames, (
        f"expected research_ended via stale-window diff; "
        f"events={[f['event'] for f in frames]}"
    )


@pytest.mark.asyncio
async def test_given_open_stream_when_heartbeat_interval_elapses_then_comment_line_emitted(
    monkeypatch,
):
    monkeypatch.setattr("backend.core.config.POLL_INTERVAL_SECONDS", 0.02)
    monkeypatch.setattr("backend.core.config.HEARTBEAT_INTERVAL_SECONDS", 0.1)
    _, app, _ = _build_service_and_app()

    async with (
        _async_client(app) as client,
        client.stream("GET", "/v1/dashboard/research/stream") as response,
    ):
        body = await _drain_response_body(response)

    assert ":heartbeat" in body, f"no :heartbeat line in body={body!r}"
    heartbeat_line = next(
        line for line in body.split("\n") if line.startswith(":heartbeat")
    )
    # Heartbeat is a comment line, not a `data:` event — clients' onmessage
    # handler must not fire on it.
    assert heartbeat_line.startswith(":heartbeat")
    assert "data:" not in heartbeat_line
    assert "event:" not in heartbeat_line


@pytest.mark.asyncio
async def test_given_reconnect_with_last_event_id_when_subscribing_then_server_emits_fresh_id_zero_snapshot():
    _, app, _ = _build_service_and_app()

    async with (
        _async_client(app) as client,
        client.stream(
            "GET",
            "/v1/dashboard/research/stream",
            headers={"Last-Event-ID": "5"},
        ) as response,
    ):
        assert response.status_code == 200
        body = await _drain_response_body(response)

    frames = _parse_frames(body)
    assert frames[0]["event"] == "snapshot"
    assert frames[0]["id"] == "0"


@pytest.mark.asyncio
async def test_given_hard_timeout_elapses_when_streaming_then_response_closes_cleanly(
    monkeypatch,
):
    # Override the autouse default for an even tighter deadline.
    monkeypatch.setattr("backend.core.config.HARD_TIMEOUT_SECONDS", 1)
    _, app, _ = _build_service_and_app()

    loop = asyncio.get_event_loop()
    start = loop.time()
    async with (
        _async_client(app) as client,
        client.stream("GET", "/v1/dashboard/research/stream") as response,
    ):
        body = await _drain_response_body(response)
    elapsed = loop.time() - start

    # 1 s hard-timeout + slack for ASGI shutdown; must not run forever.
    assert elapsed < 8.0, f"stream did not close after timeout (elapsed={elapsed})"
    assert "event: snapshot" in body


@pytest.mark.asyncio
async def test_given_five_streams_open_when_sixth_anonymous_connects_then_returns_429_rate_limit_exceeded(
    monkeypatch,
):
    # Stretch the hard timeout so the 5 holders stay open while we open the 6th.
    monkeypatch.setattr("backend.core.config.HARD_TIMEOUT_SECONDS", 5)
    _, app, _ = _build_service_and_app()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        # Open 5 concurrent streams in background tasks. Each task awaits
        # the entire generator's lifetime (HARD_TIMEOUT_SECONDS), so the
        # slot is held for the duration of each task.
        async def _hold_one() -> int:
            async with client.stream("GET", "/v1/dashboard/research/stream") as resp:
                # Drain to keep the slot until the generator naturally ends.
                async for _chunk in resp.aiter_text():
                    pass
                return resp.status_code

        holders = [asyncio.create_task(_hold_one()) for _ in range(5)]
        # Yield to let each holder reach __aenter__ and acquire its slot.
        await asyncio.sleep(0.15)

        # The 6th connection must be rejected with 429 + rate_limit_exceeded.
        sixth = await client.get("/v1/dashboard/research/stream")
        assert sixth.status_code == 429, sixth.text
        assert sixth.json() == {"error": "rate_limit_exceeded"}

        # Drain holders to keep the test deterministic.
        for h in holders:
            await h


@pytest.mark.asyncio
async def test_given_emitted_frames_when_validating_payload_keys_then_only_allowlist_present():
    service, app, author_id = _build_service_and_app()
    _seed_active_problem(service, author_id)

    allowed_snapshot_keys = {
        "active",
        "last_cycle_at",
        "recent_cycles",
        "cycles_last_7_days",
        "now",
    }
    allowed_active_keys = {
        "problem_id",
        "description",
        "solution_count",
        "best_confidence",
        "research_started_at",
        "elapsed_seconds",
    }
    forbidden_keys = {"agent_id", "reporter_id", "email", "api_key", "markdown"}

    async with (
        _async_client(app) as client,
        client.stream("GET", "/v1/dashboard/research/stream") as response,
    ):
        body = await _drain_response_body(response)

    frames = _parse_frames(body)
    snapshot = next(f for f in frames if f["event"] == "snapshot")
    payload = json.loads(snapshot["data"])
    assert set(payload.keys()) == allowed_snapshot_keys
    for forbidden in forbidden_keys:
        assert forbidden not in payload
    for item in payload["active"]:
        assert set(item.keys()) == allowed_active_keys
        for forbidden in forbidden_keys:
            assert forbidden not in item


@pytest.mark.asyncio
async def test_given_research_state_changes_when_emitting_diff_event_then_structured_log_line_recorded(
    caplog,
):
    service, app, author_id = _build_service_and_app()
    caplog.set_level(logging.INFO, logger="backend.presentation.api.routes.dashboard")

    state = {"problem_id": None}

    async def _seed_after_first_poll() -> None:
        await asyncio.sleep(0.15)
        problem = _seed_active_problem(service, author_id)
        state["problem_id"] = str(problem.problem_id)

    async with _async_client(app) as client:
        seeder = asyncio.create_task(_seed_after_first_poll())
        async with client.stream("GET", "/v1/dashboard/research/stream") as response:
            await _drain_response_body(response)
        await seeder

    sse_records = [r for r in caplog.records if r.message == "sse_event"]
    assert sse_records, "expected at least one structured sse_event log record"
    started_records = [
        r for r in sse_records if getattr(r, "event", None) == "research_started"
    ]
    assert started_records, "expected a research_started log record"
    assert any(
        getattr(r, "problem_id", None) == state["problem_id"] for r in started_records
    )


@pytest.mark.asyncio
async def test_given_repeated_polls_within_ttl_when_recomputing_snapshot_then_last_cycle_at_query_runs_once(
    monkeypatch,
):
    monkeypatch.setattr("backend.core.config.LAST_CYCLE_CACHE_TTL_SECONDS", 10.0)
    service, app, _ = _build_service_and_app()

    call_count = {"n": 0}
    original = service._research_cycles.get_latest_cycle_at

    def _counted() -> datetime | None:
        call_count["n"] += 1
        return original()

    service._research_cycles.get_latest_cycle_at = _counted  # type: ignore[assignment]

    async with (
        _async_client(app) as client,
        client.stream("GET", "/v1/dashboard/research/stream") as response,
    ):
        await _drain_response_body(response)

    # Across the entire 1 s HARD_TIMEOUT window with POLL_INTERVAL=0.05 s,
    # the underlying MAX query must run at most once thanks to the 10 s
    # in-process cache. Anything > 1 means the diff loop bypassed the cache.
    assert call_count["n"] <= 1, (
        f"last_cycle_at queried {call_count['n']} times; cache TTL not honoured"
    )


@pytest.mark.asyncio
async def test_given_configured_origin_when_browser_subscribes_then_cors_echoes_origin():
    original = app_settings.cors_allow_origins
    app_settings.cors_allow_origins = "https://agentbook.app"
    try:
        _, app, _ = _build_service_and_app()
        async with (
            _async_client(app) as client,
            client.stream(
                "GET",
                "/v1/dashboard/research/stream",
                headers={"Origin": "https://agentbook.app"},
            ) as response,
        ):
            assert response.status_code == 200
            allow_origin = response.headers.get("access-control-allow-origin")
            assert allow_origin == "https://agentbook.app"
            assert allow_origin != "*"
    finally:
        app_settings.cors_allow_origins = original
