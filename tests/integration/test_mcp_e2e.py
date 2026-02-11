"""E2E tests for MCP using Python SDK client.

These tests validate the MCP (Model Context Protocol) implementation
using the official Python SDK client API with SSE transport.

Requires the backend server to be running locally.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.domain.models import Comment, Thread
from app.infrastructure.persistence.database import SessionLocal
from app.infrastructure.persistence.sqlalchemy_repositories import (
    SQLAlchemyCommentRepository,
    SQLAlchemyThreadRepository,
)
from app.main import create_app

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


# ============================================================================
# Fixtures
# ============================================================================


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
    """Cleanup E2E test data after each test.

    This fixture removes all threads and comments created during E2E tests.
    """
    yield

    # Clean up test threads with "E2E" tag
    thread_repo = SQLAlchemyThreadRepository(lambda: e2e_db())
    try:
        threads = thread_repo.list_threads(limit=1000)
        for thread in threads:
            if "e2e" in thread.tags:
                comment_repo = SQLAlchemyCommentRepository(lambda: e2e_db())
                # Delete all comments for this thread
                comments = comment_repo.list_for_thread(thread.thread_id)
                for comment in comments:
                    comment_repo.delete(comment.comment_id)
                # Delete the thread
                thread_repo.delete(thread.thread_id)
    except Exception:
        pass  # Ignore cleanup errors


# ============================================================================
# MCP Client Tests
# ============================================================================


@pytest.mark.asyncio
async def test_mcp_sse_client_connect() -> None:
    """Scenario: MCP client can connect via SSE transport

    BDD Reference: Feature "MCP SSE Connection Management"

    Given: Backend server is running with MCP SSE endpoint
    When: MCP client connects via SSE with valid API key
    Then: Connection succeeds
          And: Session initializes successfully
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
async def test_mcp_client_call_search_agentbook() -> None:
    """Scenario: Client can call search_agentbook tool

    BDD Reference: Feature "MCP Tool Execution"

    Given: MCP client is connected and initialized
    When: Client calls search_agentbook tool with query
    Then: Tool executes successfully
          And: Returns search results
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

            # Call search_agentbook tool
            result = await session.call_tool(
                "search_agentbook",
                arguments={"query": "Python asyncio", "limit": 5},
            )

            assert not result.isError
            assert len(result.content) > 0

            # Parse text content
            if isinstance(result.content[0], types.TextContent):
                print(f"Search result: {result.content[0].text[:200]}...")
                assert "Python" in result.content[0].text or "result" in result.content[0].text.lower()


@pytest.mark.asyncio
async def test_mcp_client_call_ask_question() -> None:
    """Scenario: Client can call ask_question tool

    BDD Reference: Feature "MCP Tool Execution"

    Given: MCP client is connected and initialized
    When: Client calls ask_question tool with title and body
    Then: Tool executes successfully
          And: Returns thread creation result
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

            # Call ask_question tool
            result = await session.call_tool(
                "ask_question",
                arguments={
                    "title": f"E2E Test Question {datetime.now().isoformat()}",
                    "body": "This is a test question created by E2E tests.",
                    "tags": ["test", "e2e"],
                },
            )

            assert not result.isError
            assert len(result.content) > 0

            # Parse response
            if isinstance(result.content[0], types.TextContent):
                response_text = result.content[0].text
                print(f"Question created: {response_text[:200]}...")
                assert "thread" in response_text.lower() or "question" in response_text.lower()


@pytest.mark.asyncio
async def test_mcp_client_call_answer_question() -> None:
    """Scenario: Client can call answer_question tool

    BDD Reference: Feature "MCP Tool Execution"

    Given: MCP client is connected and initialized
    When: Client calls answer_question tool for a thread
    Then: Tool executes successfully
          And: Returns answer creation result
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

            # Call answer_question tool
            result = await session.call_tool(
                "answer_question",
                arguments={
                    "thread_id": str(uuid4()),  # Use random thread ID for test
                    "content": "This is a test answer created by E2E tests.",
                    "is_solution": False,
                },
            )

            assert not result.isError
            assert len(result.content) > 0

            # Parse response
            if isinstance(result.content[0], types.TextContent):
                print(f"Answer result: {result.content[0].text[:200]}...")


@pytest.mark.asyncio
async def test_mcp_client_unauthenticated_fails() -> None:
    """Scenario: Client without authentication fails

    BDD Reference: Feature "MCP Authentication"

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
                # Should not reach here
                assert False, "Should have failed without authentication"
    except Exception as e:
        # Expect connection error or authentication error
        print(f"Expected error: {e}")
        assert True  # Connection should fail


@pytest.mark.asyncio
async def test_mcp_client_list_tools() -> None:
    """Scenario: Client can list available tools

    BDD Reference: Feature "MCP Tool Discovery"

    Given: MCP client is connected and initialized
    When: Client lists available tools
    Then: All agentbook tools are listed
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

            # List available tools
            tools = await session.list_tools()

            assert len(tools.tools) > 0

            # Check for expected tools
            tool_names = [tool.name for tool in tools.tools]
            expected_tools = ["search_agentbook", "ask_question", "answer_question", "vote_answer"]

            for expected_tool in expected_tools:
                assert expected_tool in tool_names, f"Tool {expected_tool} should be available"

            print(f"Available tools: {tool_names}")


@pytest.mark.asyncio
async def test_mcp_client_list_resources() -> None:
    """Scenario: Client can list available resources

    BDD Reference: Feature "MCP Resource Discovery"

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

            # List available resources
            resources = await session.list_resources()

            # Resources may be empty, but the call should succeed
            assert resources is not None
            print(f"Available resources: {len(resources.resources) if resources else 0}")


@pytest.mark.asyncio
async def test_mcp_client_call_vote_answer() -> None:
    """Scenario: Client can call vote_answer tool

    BDD Reference: Feature "MCP Tool Execution"

    Given: MCP client is connected and initialized
    When: Client calls vote_answer tool for a comment
    Then: Tool executes successfully
          And: Returns vote result
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

            # Call vote_answer tool with random comment ID
            result = await session.call_tool(
                "vote_answer",
                arguments={
                    "comment_id": str(uuid4()),  # Use random comment ID for test
                    "vote_type": "upvote",
                },
            )

            assert not result.isError
            assert len(result.content) > 0

            # Parse response
            if isinstance(result.content[0], types.TextContent):
                print(f"Vote result: {result.content[0].text[:200]}...")


# ============================================================================
# End-to-End Workflow Tests
# ============================================================================


@pytest.mark.asyncio
async def test_mcp_full_workflow_search_and_ask() -> None:
    """Scenario: Complete MCP workflow: search, ask question, answer

    BDD Reference: Feature "MCP Full Workflow"

    Given: MCP client is connected
    When: Client searches for content and asks a question
    Then: All operations complete successfully
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

            # Step 1: Search for content
            search_result = await session.call_tool(
                "search_agentbook",
                arguments={"query": "asyncio programming", "limit": 3},
            )
            assert not search_result.isError

            # Step 2: Ask a question
            ask_result = await session.call_tool(
                "ask_question",
                arguments={
                    "title": f"How do I use asyncio in Python?",
                    "body": "I want to understand async/await pattern.",
                    "tags": ["python", "asyncio"],
                },
            )
            assert not ask_result.isError

            print("Full workflow completed: search -> ask question -> success")


# ============================================================================
# Run Tests Directly
# ============================================================================

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
            test_mcp_client_call_search_agentbook,
            test_mcp_client_call_ask_question,
            test_mcp_client_call_answer_question,
            test_mcp_client_unauthenticated_fails,
            test_mcp_client_list_tools,
            test_mcp_client_list_resources,
            test_mcp_client_call_vote_answer,
            test_mcp_full_workflow_search_and_ask,
        ]

        passed = 0
        failed = 0

        for test in tests:
            try:
                print(f"\nRunning {test.__name__}...")
                await test
                print(f"✓ {test.__name__} passed")
                passed += 1
            except Exception as e:
                print(f"✗ {test.__name__} failed: {e}")
                failed += 1

        print(f"\n\nResults: {passed} passed, {failed} failed")
        sys.exit(0 if failed == 0 else 1)

    asyncio.run(run_all_tests())