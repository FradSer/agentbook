"""Performance tests for MCP Streamable HTTP transport latency.

These tests measure connection establishment, throughput, and concurrent
session handling to ensure P99 latency targets are met.

BDD Reference: Feature "MCP Streamable HTTP Performance"

Performance targets:
- P99 latency < 100ms for connection establishment
- Max latency < 200ms
- Average latency < 50ms
- Throughput > 100 req/s in stateless mode
"""

from __future__ import annotations

import asyncio
import os
import statistics
import time
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from backend.domain.models import Agent
from backend.infrastructure.security import hash_api_key
from backend.main import create_app

pytestmark = [
    pytest.mark.perf,
    pytest.mark.skipif(
        os.getenv("RUN_PERF_TESTS") != "1",
        reason="Set RUN_PERF_TESTS=1 to run performance tests",
    ),
]


def calculate_percentile(values: list[float], percentile: int) -> float:
    """Calculate percentile from list of values using standard interpolation."""
    if not values:
        raise ValueError("values must not be empty")
    if len(values) == 1:
        return values[0]
    # statistics.quantiles returns n-1 cut points; index (percentile-1) gives Ppercentile
    return statistics.quantiles(sorted(values), n=100)[percentile - 1]


@pytest.fixture()
def test_agent():
    """Create test agent for performance tests."""
    api_key_hash = hash_api_key("ak_perf-test-key")
    return Agent(
        agent_id=uuid4(),
        api_key_hash=api_key_hash,
        model_type="perf-test",
        token_balance=1000,
        created_at=datetime.now(UTC),
        last_active_at=datetime.now(UTC),
    )


@pytest.fixture()
def auth_headers():
    """Authentication headers for performance tests."""
    return {
        "Authorization": "Bearer ak_perf-test-key",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }


@pytest.fixture()
def mcp_initialize_request():
    """MCP initialize JSON-RPC request."""
    return {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "perf-test", "version": "1.0.0"},
        },
        "id": 1,
    }


@pytest.mark.asyncio
async def test_connection_establishment_p99_latency(
    test_agent, auth_headers, mcp_initialize_request
):
    """Test P99 latency for connection establishment is under 100ms.

    BDD Scenario: Connection establishment latency meets P99 target
      Given client sends 100 consecutive POST requests to establish sessions
      When measuring response times
      Then P99 latency is less than 100ms
      And no request exceeds 200ms
      And average latency is less than 50ms
    """
    app = create_app()

    # Register test agent
    app.state.service.agent_repo.add(test_agent)

    transport = httpx.ASGITransport(app=app)
    latencies: list[float] = []

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Warm-up requests
        for _ in range(10):
            await client.post("/mcp", headers=auth_headers, json=mcp_initialize_request)

        # Measure 100 requests
        for _ in range(100):
            start_time = time.perf_counter()
            response = await client.post(
                "/mcp", headers=auth_headers, json=mcp_initialize_request
            )
            end_time = time.perf_counter()

            assert response.status_code == 200
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

    # Calculate statistics
    p99 = calculate_percentile(latencies, 99)
    max_latency = max(latencies)
    avg_latency = statistics.mean(latencies)

    print("\nConnection Establishment Latency:")
    print(f"  P99: {p99:.2f}ms")
    print(f"  Max: {max_latency:.2f}ms")
    print(f"  Avg: {avg_latency:.2f}ms")

    # Assert performance targets
    assert p99 < 100, f"P99 latency {p99:.2f}ms exceeds 100ms target"
    assert max_latency < 200, f"Max latency {max_latency:.2f}ms exceeds 200ms target"
    assert avg_latency < 50, f"Avg latency {avg_latency:.2f}ms exceeds 50ms target"


@pytest.mark.asyncio
async def test_stateless_mode_throughput(
    test_agent, auth_headers, mcp_initialize_request
):
    """Test throughput in stateless mode exceeds 100 req/s.

    BDD Scenario: Stateless mode throughput
      Given StreamableHTTPSessionManager is configured with stateless=true
      When client sends 1000 requests
      Then throughput exceeds 100 requests per second
    """
    app = create_app()

    # Register test agent
    app.state.service.agent_repo.add(test_agent)

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Warm-up
        for _ in range(10):
            await client.post("/mcp", headers=auth_headers, json=mcp_initialize_request)

        # Measure throughput
        num_requests = 1000
        start_time = time.perf_counter()

        tasks = [
            client.post("/mcp", headers=auth_headers, json=mcp_initialize_request)
            for _ in range(num_requests)
        ]
        responses = await asyncio.gather(*tasks)

        end_time = time.perf_counter()
        duration = end_time - start_time

        # Verify all requests succeeded
        assert all(r.status_code == 200 for r in responses)

        throughput = num_requests / duration
        print("\nStateless Mode Throughput:")
        print(f"  Requests: {num_requests}")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Throughput: {throughput:.2f} req/s")

        assert throughput > 100, (
            f"Throughput {throughput:.2f} req/s below 100 req/s target"
        )


@pytest.mark.asyncio
async def test_concurrent_sessions(test_agent, auth_headers, mcp_initialize_request):
    """Test concurrent session creation completes within 5 seconds.

    BDD Scenario: Concurrent sessions
      Given client creates 50 concurrent sessions
      When measuring completion time
      Then all sessions succeed within 5 seconds
      And latency distribution is reasonable
    """
    app = create_app()

    # Register test agent
    app.state.service.agent_repo.add(test_agent)

    transport = httpx.ASGITransport(app=app)
    num_sessions = 50

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        start_time = time.perf_counter()

        # Create concurrent sessions
        tasks = [
            client.post("/mcp", headers=auth_headers, json=mcp_initialize_request)
            for _ in range(num_sessions)
        ]
        responses = await asyncio.gather(*tasks)

        end_time = time.perf_counter()
        duration = end_time - start_time

        # Verify all succeeded
        assert all(r.status_code == 200 for r in responses)

        print("\nConcurrent Sessions:")
        print(f"  Sessions: {num_sessions}")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Avg per session: {(duration / num_sessions) * 1000:.2f}ms")

        assert duration < 5.0, (
            f"Concurrent sessions took {duration:.2f}s, exceeds 5s target"
        )
