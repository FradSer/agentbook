"""Verifies the contract in features/rate_limit_retry_after.feature.

Every 429 surface in agentbook must include both an HTTP ``Retry-After``
header and a structured ``error.details.retry_after_seconds`` field.
Without it the agent has to guess and a too-short guess immediately
re-trips the bucket — a 429 with no hint is a 429 the agent cannot
recover from automatically.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from backend.application.errors import RateLimitError
from backend.core.mcp_rate_limit import MCPRateLimiter
from backend.tests.conftest import _build_client

# ---------------------------------------------------------------------------
# MCP in-process limiter exposes retry_after directly.
# ---------------------------------------------------------------------------


class TestMCPRateLimiterRetryAfter:
    def test_retry_after_returns_zero_for_unknown_key(self) -> None:
        limiter = MCPRateLimiter(max_calls=3, window_seconds=60)
        assert limiter.retry_after("never-seen") == 0

    def test_retry_after_returns_zero_when_bucket_has_room(self) -> None:
        limiter = MCPRateLimiter(max_calls=3, window_seconds=60)
        limiter.hit("k")
        # Two more allowed; not yet throttled.
        assert limiter.retry_after("k") == 0

    def test_retry_after_returns_seconds_until_oldest_hit_ages_out(self) -> None:
        limiter = MCPRateLimiter(max_calls=3, window_seconds=60)
        for _ in range(3):
            limiter.hit("k")
        wait = limiter.retry_after("k")
        # Oldest hit is brand-new, so window ~= 60s remaining; allow a small
        # scheduler jitter envelope.
        assert 55 <= wait <= 60

    def test_retry_after_floor_is_one_second(self) -> None:
        """A throttled bucket should never advise 0 — that just re-trips."""
        limiter = MCPRateLimiter(max_calls=1, window_seconds=2)
        limiter.hit("k")
        time.sleep(1.5)
        wait = limiter.retry_after("k")
        assert wait >= 1


# ---------------------------------------------------------------------------
# REST 429s (slowapi-driven and domain-driven) include Retry-After header.
# ---------------------------------------------------------------------------


class TestRESTSearchRetryAfter:
    def test_search_429_includes_retry_after_header_and_field(
        self, enable_limiter
    ) -> None:
        client, _ = _build_client()
        # Burn the 30/min anonymous bucket on /v1/search.
        for _ in range(30):
            client.get("/v1/search", params={"q": "x"})
        resp = client.get("/v1/search", params={"q": "x"})
        assert resp.status_code == 429, (
            f"Expected 429 after burning the 30/min bucket, got {resp.status_code}"
        )
        retry_after = resp.headers.get("Retry-After")
        assert retry_after is not None, (
            "RFC 6585 §4: 429 SHOULD include Retry-After. Without it agents "
            "guess wrong and immediately re-trip the bucket."
        )
        assert retry_after.isdigit() and 1 <= int(retry_after) <= 60
        body = resp.json()
        assert body["error"]["details"]["retry_after_seconds"] == int(retry_after)


class TestRESTRegisterRetryAfter:
    def test_register_429_includes_retry_after_header_within_one_hour(
        self, enable_limiter
    ) -> None:
        client, _ = _build_client()
        # Burn the 10/hour register bucket.
        for i in range(10):
            client.post("/v1/auth/register", json={"model_type": f"m-{i}"})
        resp = client.post("/v1/auth/register", json={"model_type": "m-final"})
        assert resp.status_code == 429
        retry_after = resp.headers.get("Retry-After")
        assert retry_after is not None
        seconds = int(retry_after)
        assert 1 <= seconds <= 3600


class TestDomainRateLimitErrorHandler:
    """Domain RateLimitError handler must propagate the carrier's hint."""

    def test_rate_limit_error_with_explicit_retry_after_propagates_to_response(
        self,
    ) -> None:
        from fastapi import FastAPI

        from backend.main import _install_domain_error_handlers

        app = FastAPI()
        _install_domain_error_handlers(app)

        @app.get("/explode")
        def _explode() -> None:
            raise RateLimitError("outcome reporting saturated", retry_after_seconds=42)

        client = TestClient(app)
        resp = client.get("/explode")
        assert resp.status_code == 429
        assert resp.headers.get("Retry-After") == "42"
        assert resp.json()["error"]["details"]["retry_after_seconds"] == 42

    def test_rate_limit_error_without_hint_falls_back_to_default_window(self) -> None:
        from fastapi import FastAPI

        from backend.main import _install_domain_error_handlers

        app = FastAPI()
        _install_domain_error_handlers(app)

        @app.get("/explode")
        def _explode() -> None:
            raise RateLimitError("outcome reporting saturated")

        client = TestClient(app)
        resp = client.get("/explode")
        assert resp.status_code == 429
        retry_after = resp.headers.get("Retry-After")
        assert retry_after is not None and int(retry_after) >= 1


# ---------------------------------------------------------------------------
# MCP recall 429 payload carries retry_after_seconds.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_recall_429_payload_contains_retry_after_seconds(
    enable_mcp_limiter,
) -> None:
    from unittest.mock import MagicMock

    from mcp.server import Server

    from backend.presentation.mcp.context import current_remote_addr
    from backend.presentation.mcp.tools import dispatch_tool

    service = MagicMock()
    service.search_problems.return_value = {"results": [], "total": 0}
    server = Server("retry-after-test")
    server._service = service

    current_remote_addr.set("198.51.100.42")

    async def call() -> dict:
        result = await dispatch_tool(server, "recall", {"query": "x"})
        return json.loads(result[0]["text"])

    for _ in range(30):
        await call()
    throttled = await call()
    assert throttled["error"] == "rate_limit_exceeded"
    assert isinstance(throttled.get("retry_after_seconds"), int)
    assert 1 <= throttled["retry_after_seconds"] <= 60
