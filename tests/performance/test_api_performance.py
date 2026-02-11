from __future__ import annotations

import asyncio
import os
import statistics
import time
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from app.core.config import settings
from app.main import create_app

pytestmark = [
    pytest.mark.perf,
    pytest.mark.skipif(
        os.getenv("RUN_PERF_TESTS") != "1",
        reason="Set RUN_PERF_TESTS=1 to run performance checks",
    ),
]


async def register_agent(client: httpx.AsyncClient, model_type: str = "claude") -> dict:
    response = await client.post("/v1/auth/register", json={"model_type": model_type})
    assert response.status_code == 201
    return response.json()


def auth_headers(api_key: str, model_name: str = "perf") -> dict[str, str]:
    return {
        "X-API-Key": api_key,
        "X-Agent-Info": f'{{"model":"{model_name}","platform":"benchmark"}}',
    }


def p95(values: list[float]) -> float:
    if not values:
        raise ValueError("values must not be empty")
    return statistics.quantiles(values, n=100, method="inclusive")[94]


def approve_thread(app, thread_id: str) -> None:
    app.state.service.update_thread_review(
        thread_id=UUID(thread_id),
        status="approved",
        score=8.0,
        reviewed_at=datetime.now(UTC),
    )


def approve_comment(app, comment_id: str) -> None:
    app.state.service.update_comment_review(
        comment_id=UUID(comment_id),
        status="approved",
        score=8.0,
        reviewed_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_api_response_p95_under_200ms() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        author = await register_agent(client)
        headers = auth_headers(author["api_key"])

        for index in range(60):
            response = await client.post(
                "/v1/threads",
                headers=headers,
                json={"title": f"thread-{index}", "body": "body", "tags": ["perf"]},
            )
            assert response.status_code == 201
            approve_thread(app, response.json()["thread_id"])

        latencies: list[float] = []
        for _ in range(100):
            started_at = time.perf_counter()
            response = await client.get(
                "/v1/threads", headers=headers, params={"limit": 20}
            )
            latencies.append(time.perf_counter() - started_at)
            assert response.status_code == 200

        assert p95(latencies) < 0.2


@pytest.mark.asyncio
async def test_search_p95_under_500ms() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        author = await register_agent(client)
        headers = auth_headers(author["api_key"])

        for index in range(120):
            response = await client.post(
                "/v1/threads",
                headers=headers,
                json={
                    "title": f"fastmcp import issue {index}",
                    "body": "ModuleNotFoundError fastmcp",
                    "tags": ["python", "mcp"],
                },
            )
            assert response.status_code == 201
            approve_thread(app, response.json()["thread_id"])

        latencies: list[float] = []
        for _ in range(80):
            start = time.perf_counter()
            response = await client.get(
                "/v1/search",
                headers=headers,
                params={"q": "fastmcp", "limit": 10},
            )
            elapsed = time.perf_counter() - start
            assert response.status_code == 200
            latencies.append(elapsed)

        assert p95(latencies) < 0.5


@pytest.mark.asyncio
async def test_supports_100_concurrent_requests() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        author = await register_agent(client)
        headers = auth_headers(author["api_key"])

        thread_response = await client.post(
            "/v1/threads",
            headers=headers,
            json={"title": "concurrency", "body": "body", "tags": ["perf"]},
        )
        assert thread_response.status_code == 201

        async def one_request() -> int:
            response = await client.get("/v1/threads", headers=headers)
            return response.status_code

        statuses = await asyncio.gather(*[one_request() for _ in range(120)])
        assert all(status == 200 for status in statuses)


@pytest.mark.asyncio
async def test_supports_100_concurrent_vote_requests() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        author = await register_agent(client, model_type="claude")
        author_headers = auth_headers(author["api_key"], "claude")

        thread_response = await client.post(
            "/v1/threads",
            headers=author_headers,
            json={"title": "vote-load", "body": "body", "tags": ["perf"]},
        )
        assert thread_response.status_code == 201
        thread_id = thread_response.json()["thread_id"]
        approve_thread(app, thread_id)

        comment_response = await client.post(
            f"/v1/threads/{thread_id}/comments",
            headers=author_headers,
            json={"content": "solution", "is_solution": True},
        )
        assert comment_response.status_code == 201
        comment_id = comment_response.json()["comment_id"]
        approve_comment(app, comment_id)

        voters = [await register_agent(client, model_type="voter") for _ in range(120)]
        voter_headers = [
            auth_headers(voter["api_key"], f"voter-{index}")
            for index, voter in enumerate(voters)
        ]

        async def vote_once(headers: dict[str, str]) -> tuple[int, float]:
            started_at = time.perf_counter()
            response = await client.post(
                f"/v1/threads/comments/{comment_id}/vote",
                headers=headers,
                json={"vote_type": "upvote"},
            )
            return response.status_code, time.perf_counter() - started_at

        results = await asyncio.gather(
            *[vote_once(headers) for headers in voter_headers]
        )
        statuses = [status for status, _ in results]
        latencies = [latency for _, latency in results]

        assert all(status == 200 for status in statuses)
        assert p95(latencies) < 0.5

        detail_response = await client.get(
            f"/v1/threads/{thread_id}", headers=author_headers
        )
        assert detail_response.status_code == 200
        comments = detail_response.json()["comments"]
        assert comments[0]["upvotes"] == 120


@pytest.mark.smoke
@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_REAL_EMBED_TESTS") != "1" or not os.getenv("OPENROUTER_API_KEY"),
    reason="Set RUN_REAL_EMBED_TESTS=1 and OPENROUTER_API_KEY for real embedding check",
)
async def test_search_latency_with_real_openrouter_embedding() -> None:
    original_api_key = settings.openrouter_api_key
    original_model = settings.openrouter_embedding_model
    settings.openrouter_api_key = os.environ["OPENROUTER_API_KEY"]
    if os.getenv("OPENROUTER_EMBEDDING_MODEL"):
        settings.openrouter_embedding_model = os.environ["OPENROUTER_EMBEDDING_MODEL"]

    try:
        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            author = await register_agent(client)
            headers = auth_headers(author["api_key"], "real-embed")

            thread_response = await client.post(
                "/v1/threads",
                headers=headers,
                json={
                    "title": "FastMCP import failure",
                    "body": "ModuleNotFoundError no module named fastmcp",
                    "tags": ["python", "mcp"],
                    "error_log": "ModuleNotFoundError: fastmcp",
                },
            )
            assert thread_response.status_code == 201
            approve_thread(app, thread_response.json()["thread_id"])

            latencies: list[float] = []
            for _ in range(5):
                started_at = time.perf_counter()
                response = await client.get(
                    "/v1/search",
                    headers=headers,
                    params={"q": "fastmcp importerror", "limit": 5},
                )
                latencies.append(time.perf_counter() - started_at)
                assert response.status_code == 200
                payload = response.json()
                assert payload["total"] >= 1

            # Real network call is variable; keep threshold strict enough to catch regressions
            # while allowing internet jitter in CI/local runs.
            assert p95(latencies) < 5.0
    finally:
        settings.openrouter_api_key = original_api_key
        settings.openrouter_embedding_model = original_model
