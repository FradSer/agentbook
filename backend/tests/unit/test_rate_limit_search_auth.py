"""Authenticated callers get a higher quota (300/min) than anonymous (30/min)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.core.mcp_rate_limit import (
    mcp_rate_key,
    mcp_search_limiter,
    mcp_search_limiter_auth,
)
from backend.domain.models import Agent
from backend.tests.conftest import _build_client


def test_given_authenticated_rest_caller_when_exceeding_300_per_minute_then_remaining_requests_are_throttled(
    enable_limiter,
):
    client, api_key = _build_client()
    headers = {"Authorization": f"Bearer {api_key}"}

    statuses = [
        client.get("/v1/search", params={"q": f"q-{i}"}, headers=headers).status_code
        for i in range(305)
    ]

    success_count = sum(1 for s in statuses if s == 200)
    rate_limited_count = sum(1 for s in statuses if s == 429)

    assert success_count == 300, (
        f"Authenticated quota should be exactly 300/min, got {success_count} successes"
    )
    assert rate_limited_count == 5, (
        f"Expected the remaining 5 calls to be rate-limited, got {rate_limited_count}"
    )


@pytest.mark.parametrize(
    ("agent", "remote_addr", "attempts", "expected_successes"),
    [
        (None, "127.0.0.1", 35, 30),
        (
            Agent(
                api_key_hash="hash",
                model_type="test",
                agent_id=uuid4(),
            ),
            None,
            305,
            300,
        ),
    ],
)
def test_given_mcp_identity_tier_when_hitting_quota_then_successes_match_configured_limit(
    enable_mcp_limiters,
    agent: Agent | None,
    remote_addr: str | None,
    attempts: int,
    expected_successes: int,
):
    key = mcp_rate_key(agent, remote_addr)
    limiter_to_use = mcp_search_limiter_auth if agent else mcp_search_limiter
    successes = sum(1 for _ in range(attempts) if limiter_to_use.hit(key))
    assert successes == expected_successes
