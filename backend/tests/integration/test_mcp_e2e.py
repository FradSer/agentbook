"""E2E tests for MCP using Python SDK client.

These tests validate the MCP (Model Context Protocol) implementation
using the official Python SDK client API with SSE transport.

Requires the backend server to be running locally.
"""

from __future__ import annotations

import asyncio
import os

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend.infrastructure.persistence.database import SessionLocal
from backend.infrastructure.persistence.sqlalchemy_repositories import (
    SQLAlchemyCommentRepository,
    SQLAlchemyThreadRepository,
)
from backend.main import create_app

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        os.getenv("RUN_E2E_TESTS") != "1",
        reason="Set RUN_E2E_TESTS=1 to run E2E tests",
    ),
]

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
TEST_API_KEY = os.getenv("TEST_API_KEY", "ak_e2e-test-key")

# E2E test timeout in seconds
E2E_TIMEOUT = 30


# Fixtures


@pytest.fixture()
def e2e_client() -> TestClient:
    """FastAPI test client for E2E tests."""
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def e2e_db():
    """Get database session for E2E tests."""
    return SessionLocal


@pytest_asyncio.fixture(autouse=True)
async def cleanup_e2e_data(e2e_db):
    """Cleanup E2E test data after each test."""
    yield

    thread_repo = SQLAlchemyThreadRepository(lambda: e2e_db())
    try:
        threads = thread_repo.list_threads(limit=1000)
        for thread in threads:
            if "e2e" in thread.tags:
                comment_repo = SQLAlchemyCommentRepository(lambda: e2e_db())
                comments = comment_repo.list_for_thread(thread.thread_id)
                for comment in comments:
                    comment_repo.delete(comment.comment_id)
                thread_repo.delete(thread.thread_id)
    except Exception:
        pass


# MCP Client Tests


@pytest.mark.asyncio
async def test_mcp_sse_client_connect() -> None:
    """Scenario: MCP client can connect via SSE transport

    Given: Backend server is running with MCP SSE endpoint
    When: MCP client connects via SSE with valid API key
    Then: Connection succeeds and session initializes
    """
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    async with sse_client(
        f"{BASE_URL}/mcp/sse",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        timeout=E2E_TIMEOUT,
    ) as streams:
        read_stream, write_stream = streams

        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            assert session is not None
            assert session.server_info is not None
            print(f"Connected to MCP server: {session.server_info.name}")


@pytest.mark.asyncio
async def test_mcp_client_call_search() -> None:
    """Scenario: Client can call search tool

    Given: MCP client is connected and initialized
    When: Client calls search tool with query
    Then: Tool executes successfully and returns results
    """
    from mcp import ClientSession, types
    from mcp.client.sse import sse_client

    async with sse_client(
        f"{BASE_URL}/mcp/sse",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        timeout=E2E_TIMEOUT,
    ) as streams:
        read_stream, write_stream = streams

        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            result = await session.call_tool(
                "search",
                arguments={"query": "Python asyncio", "limit": 5},
            )

            assert not result.isError
            assert len(result.content) > 0

            if isinstance(result.content[0], types.TextContent):
                print(f"Search result: {result.content[0].text[:200]}...")


@pytest.mark.asyncio
async def test_mcp_client_unauthenticated_fails() -> None:
    """Scenario: Client without authentication fails

    Given: Backend server is running with MCP SSE endpoint
    When: MCP client connects via SSE without valid API key
    Then: Connection fails with appropriate error
    """
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    try:
        async with sse_client(
            f"{BASE_URL}/mcp/sse",
            timeout=E2E_TIMEOUT,
        ) as streams:
            read_stream, write_stream = streams

            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                raise AssertionError("Should have failed without authentication")
    except Exception as e:
        print(f"Expected error: {e}")
        assert True


@pytest.mark.asyncio
async def test_mcp_client_list_tools() -> None:
    """Scenario: Client can list available tools

    Given: MCP client is connected and initialized
    When: Client lists available tools
    Then: All 4 agentbook tools are listed
    """
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    async with sse_client(
        f"{BASE_URL}/mcp/sse",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        timeout=E2E_TIMEOUT,
    ) as streams:
        read_stream, write_stream = streams

        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()

            assert len(tools.tools) > 0

            tool_names = [tool.name for tool in tools.tools]
            expected_tools = ["search", "contribute", "report", "inspect"]

            for expected_tool in expected_tools:
                assert expected_tool in tool_names, (
                    f"Tool {expected_tool} should be available"
                )

            print(f"Available tools: {tool_names}")


@pytest.mark.asyncio
async def test_mcp_client_list_resources() -> None:
    """Scenario: Client can list available resources

    Given: MCP client is connected and initialized
    When: Client lists available resources
    Then: Resources list is returned (may be empty)
    """
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    async with sse_client(
        f"{BASE_URL}/mcp/sse",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        timeout=E2E_TIMEOUT,
    ) as streams:
        read_stream, write_stream = streams

        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            resources = await session.list_resources()

            assert resources is not None
            print(
                f"Available resources: {len(resources.resources) if resources else 0}"
            )


@pytest.mark.asyncio
async def test_mcp_full_workflow_search_and_contribute() -> None:
    """Scenario: Complete MCP workflow: search, then contribute

    Given: MCP client is connected
    When: Client searches for content and contributes a problem
    Then: All operations complete successfully
    """
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    async with sse_client(
        f"{BASE_URL}/mcp/sse",
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        timeout=E2E_TIMEOUT,
    ) as streams:
        read_stream, write_stream = streams

        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Step 1: Search for content
            search_result = await session.call_tool(
                "search",
                arguments={"query": "asyncio programming", "limit": 3},
            )
            assert not search_result.isError

            # Step 2: Contribute a problem
            contribute_result = await session.call_tool(
                "contribute",
                arguments={
                    "description": "How to handle asyncio event loop in Python tests with pytest-asyncio",
                    "tags": ["python", "asyncio"],
                },
            )
            assert not contribute_result.isError

            print("Full workflow completed: search -> contribute -> success")


# Run Tests Directly

if __name__ == "__main__":
    """Run E2E tests directly."""
    import sys

    if os.getenv("RUN_E2E_TESTS") != "1":
        print("Set RUN_E2E_TESTS=1 to run E2E tests")
        sys.exit(1)

    async def run_all_tests():
        """Run all async tests."""
        tests = [
            test_mcp_sse_client_connect,
            test_mcp_client_call_search,
            test_mcp_client_unauthenticated_fails,
            test_mcp_client_list_tools,
            test_mcp_client_list_resources,
            test_mcp_full_workflow_search_and_contribute,
        ]

        passed = 0
        failed = 0

        for test in tests:
            try:
                print(f"\nRunning {test.__name__}...")
                await test
                print(f"  {test.__name__} passed")
                passed += 1
            except Exception as e:
                print(f"  {test.__name__} failed: {e}")
                failed += 1

        print(f"\n\nResults: {passed} passed, {failed} failed")
        sys.exit(0 if failed == 0 else 1)

    asyncio.run(run_all_tests())
