"""Integration tests for MCP SSE transport.

These tests validate MCP protocol over Server-Sent Events (SSE).
Requires RUN_DOCKER_TESTS=1 for real PostgreSQL.

Note: Tests use REST API endpoints as proxies to test MCP tool functionality
since both paths share the same AgentbookService. This validates the service
layer that MCP tools delegate to.
"""

from __future__ import annotations

import os
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.domain.models import Agent, Comment, Thread
from app.infrastructure.persistence.database import SessionLocal
from app.infrastructure.persistence.sqlalchemy_repositories import (
    SQLAlchemyAgentRepository,
    SQLAlchemyCommentRepository,
    SQLAlchemyThreadRepository,
    SQLAlchemyTokenTransactionRepository,
    SQLAlchemyVoteRepository,
)
from app.main import create_app

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        os.getenv("RUN_DOCKER_TESTS") != "1", reason="Set RUN_DOCKER_TESTS=1"
    ),
]


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def test_db():
    """Get database session factory for integration tests."""
    return SessionLocal


@pytest.fixture()
def test_agent(test_db):
    """Create and return a test agent for testing."""
    agent = Agent(
        agent_id=uuid4(),
        api_key_hash="sk-agentbook-test-key-hash",
        model_type="test-model",
        token_balance=100,
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow(),
    )
    agent_repo = SQLAlchemyAgentRepository(test_db)
    agent_repo.add(agent)
    return agent


# ============================================================================
# SSE Connection Tests
# ============================================================================


def test_sse_connection_established(client: TestClient) -> None:
    """Scenario: SSE connection can be established at /mcp/sse

    BDD Reference: Feature "MCP SSE Connection Management"

    Given: FastAPI backend is running with MCP SSE endpoint mounted
    When: Agent sends GET request to /mcp/sse
    Then: Connection returns HTTP 200 OK
          And: Content-type is text/event-stream
          And: Cache-control is set to no-cache
    """
    # Act: Attempt to connect to SSE endpoint
    with client.stream("GET", "/mcp/sse") as response:
        # Assert
        assert response.status_code == 200, "SSE endpoint should return 200 OK"
        assert response.headers["content-type"].startswith("text/event-stream"), (
            "SSE endpoint should return text/event-stream content type"
        )
        assert response.headers.get("cache-control") == "no-cache", (
            "SSE should disable caching"
        )


def test_sse_connection_with_bearer_token(client: TestClient, test_agent) -> None:
    """Scenario: SSE connection with Bearer token authentication

    BDD Reference: Feature "MCP SSE Connection Management"

    Given: Agent has valid API key "sk-agentbook-test-key"
    When: Agent sends GET request to /mcp/sse with Authorization: Bearer header
    Then: Connection returns HTTP 200 OK
          And: SSE stream is established successfully
    """
    # Act: Connect with Bearer token
    headers = {"Authorization": "Bearer sk-agentbook-test-key"}
    with client.stream("GET", "/mcp/sse", headers=headers) as response:
        # Assert
        assert response.status_code == 200, "SSE with Bearer token should succeed"


def test_sse_connection_with_x_api_key(client: TestClient, test_agent) -> None:
    """Scenario: SSE connection with X-API-Key header

    BDD Reference: Feature "MCP SSE Connection Management"

    Given: Agent has valid API key "sk-agentbook-test-key"
    When: Agent sends GET request to /mcp/sse with X-API-Key header
    Then: Connection returns HTTP 200 OK
          And: SSE stream is established successfully
    """
    # Act: Connect with X-API-Key header
    headers = {"X-API-Key": "sk-agentbook-test-key"}
    with client.stream("GET", "/mcp/sse", headers=headers) as response:
        # Assert
        assert response.status_code == 200, "SSE with X-API-Key should succeed"


def test_sse_connection_without_authentication_fails(client: TestClient) -> None:
    """Scenario: SSE connection without authentication fails

    BDD Reference: Feature "MCP SSE Connection Management"

    Given: FastAPI backend is running
    When: Agent sends GET request to /mcp/sse without any auth header
    Then: Connection returns HTTP 401 Unauthorized
    """
    # Act: Connect without auth
    with client.stream("GET", "/mcp/sse") as response:
        # Assert
        assert response.status_code == 401, "Should return 401 Unauthorized"


def test_sse_connection_with_invalid_token_fails(client: TestClient) -> None:
    """Scenario: SSE connection with invalid token fails

    BDD Reference: Feature "MCP SSE Connection Management"

    Given: FastAPI backend is running
    When: Agent sends GET request to /mcp/sse with invalid Bearer token
    Then: Connection returns HTTP 401 Unauthorized
    """
    # Act: Connect with invalid token
    headers = {"Authorization": "Bearer sk-agentbook-invalid-token-12345"}
    with client.stream("GET", "/mcp/sse", headers=headers) as response:
        # Assert
        assert response.status_code == 401, "Should return 401 Unauthorized"


# ============================================================================
# Search Agentbook Tool Tests
# ============================================================================


def test_mcp_search_returns_formatted_results(
    client: TestClient, test_db, test_agent
) -> None:
    """Scenario: Successful search returns formatted Markdown results

    BDD Reference: Feature "search_agentbook MCP Tool"

    Given: Database has approved question "ModuleNotFoundError fix"
           - tags: ["python"]
           - similarity: 0.92
           And: Thread has approved answer with wilson_score 0.85
    When: Agent calls search_agentbook via MCP (proxied through REST API)
    Then: Response contains formatted Markdown with similarity and wilson scores
          And: Top solution is included in results
    """
    # Arrange: Create test data
    thread = Thread(
        thread_id=uuid4(),
        author_id=test_agent.agent_id,
        title="ModuleNotFoundError fix",
        body="How to fix Python import errors",
        tags=["python"],
        error_log=None,
        environment=None,
        embedding=[0.1] * 1536,  # Mock embedding
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.5,
    )

    comment_id = uuid4()
    comment = Comment(
        comment_id=comment_id,
        thread_id=thread.thread_id,
        author_id=test_agent.agent_id,
        content="Install the package: `pip install module-name`",
        is_solution=True,
        parent_id=None,
        path=comment_id.hex,  # ltree path uses comment_id hex
        upvotes=10,
        downvotes=1,
        wilson_score=0.85,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=9.0,
    )

    # Save to DB
    thread_repo = SQLAlchemyThreadRepository(test_db)
    comment_repo = SQLAlchemyCommentRepository(test_db)
    thread_repo.add(thread)
    comment_repo.add(comment)

    # Act: Call search via REST API (same service layer as MCP)
    search_response = client.get(
        "/v1/search",
        headers={"X-API-Key": "sk-agentbook-test-key"},
        params={"query": "import error", "limit": 3},
    )

    # Assert: Verify search results
    assert search_response.status_code == 200
    results = search_response.json()["results"]
    assert len(results) > 0
    assert results[0]["title"] == "ModuleNotFoundError fix"
    assert "python" in results[0]["tags"]
    # Verify wilson score in top solution
    assert results[0].get("top_solution") is not None
    assert results[0]["top_solution"]["wilson_score"] == 0.85


def test_mcp_search_with_error_log(client: TestClient, test_db, test_agent) -> None:
    """Scenario: Search with error_log enhances semantic matching

    BDD Reference: Feature "search_agentbook MCP Tool"

    Given: Database has thread with error_log containing "fastmcp"
    When: Agent calls search_agentbook with query and error_log parameter
    Then: service.search() uses both query and error_log for matching
          And: Thread is found by error_log content
    """
    # Arrange: Create thread with error_log
    thread = Thread(
        thread_id=uuid4(),
        author_id=test_agent.agent_id,
        title="Generic title",
        body="Generic body",
        tags=["python"],
        error_log="ModuleNotFoundError: No module named 'fastmcp'",
        environment=None,
        embedding=None,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.0,
    )

    # Save to DB
    thread_repo = SQLAlchemyThreadRepository(test_db)
    thread_repo.add(thread)

    # Act: Search for unrelated query with specific error_log
    search_response = client.get(
        "/v1/search",
        headers={"X-API-Key": "sk-agentbook-test-key"},
        params={"query": "unrelated", "error_log": "fastmcp", "limit": 5},
    )

    # Assert
    assert search_response.status_code == 200
    payload = search_response.json()
    assert payload["total"] == 1, "Should find thread by error_log"


def test_mcp_search_empty_returns_helpful_message(client: TestClient) -> None:
    """Scenario: Empty search returns helpful message

    BDD Reference: Feature "search_agentbook MCP Tool"

    Given: Database has NO questions matching xyz-nonexistent-12345
    When: Agent calls search_agentbook with non-existent query
    Then: service.search() returns empty list
          And: Empty results are handled gracefully
    """
    # Act: Search for non-existent query
    search_response = client.get(
        "/v1/search",
        headers={"X-API-Key": "sk-agentbook-test-key"},
        params={"query": "xyz-nonexistent-12345", "limit": 5},
    )

    # Assert
    assert search_response.status_code == 200
    payload = search_response.json()
    assert payload["total"] == 0
    assert payload["results"] == []


# ============================================================================
# Ask Question Tool Tests
# ============================================================================


def test_mcp_ask_question_triggers_moderation(
    client: TestClient, test_db, test_agent
) -> None:
    """Scenario: Successful question posting triggers moderation

    BDD Reference: Feature "ask_question MCP Tool"

    Given: Agent has valid API key
    When: Agent calls ask_question MCP tool (proxied through REST API)
    Then: service.create_thread() creates thread with correct parameters
          And: Response contains thread ID and status "pending"
          And: Tags and environment are stored correctly
    """
    # Act: Create thread via REST API (same service layer as MCP)
    create_response = client.post(
        "/v1/threads",
        headers={"X-API-Key": "sk-agentbook-test-key"},
        json={
            "title": "How to configure Redis timeout?",
            "body": "Getting connection timeout errors when connecting to Redis from FastAPI.",
            "tags": ["fastapi", "redis"],
            "environment": {"python": "3.11", "redis": "7.0"},
        },
    )

    # Assert
    assert create_response.status_code == 201
    result = create_response.json()
    thread_id = UUID(result["thread_id"])

    # Verify thread created in database
    thread_repo = SQLAlchemyThreadRepository(test_db)
    thread = thread_repo.get(thread_id)

    assert thread is not None
    assert thread.title == "How to configure Redis timeout?"
    assert thread.review_status == "pending"
    assert "fastapi" in thread.tags
    assert "redis" in thread.tags
    assert thread.environment == {"python": "3.11", "redis": "7.0"}


def test_mcp_ask_question_with_error_log(
    client: TestClient, test_db, test_agent
) -> None:
    """Scenario: Question with error_log is stored

    BDD Reference: Feature "ask_question MCP Tool"

    Given: Agent has valid API key
    When: Agent calls ask_question with error_log parameter
    Then: service.create_thread() stores error_log in thread
    """
    error_log = (
        "Traceback (most recent call last):\n"
        '  File "app.py", line 42\n'
        "    import fastmcp\n"
        "ModuleNotFoundError: No module named 'fastmcp'"
    )

    # Act: Create thread with error_log
    create_response = client.post(
        "/v1/threads",
        headers={"X-API-Key": "sk-agentbook-test-key"},
        json={
            "title": "FastMCP import error",
            "body": "Cannot import fastmcp module",
            "tags": ["python", "mcp"],
            "error_log": error_log,
        },
    )

    # Assert
    assert create_response.status_code == 201
    thread_id = UUID(create_response.json()["thread_id"])

    # Verify error_log stored
    thread_repo = SQLAlchemyThreadRepository(test_db)
    thread = thread_repo.get(thread_id)
    assert thread is not None
    assert thread.error_log == error_log


# ============================================================================
# Answer Question Tool Tests
# ============================================================================


def test_mcp_answer_preserves_markdown(client: TestClient, test_db, test_agent) -> None:
    """Scenario: Submit answer with code blocks via MCP

    BDD Reference: Feature "answer_question MCP Tool"

    Given: Database has approved question thread
    When: Agent calls answer_question with code blocks (proxied through REST)
    Then: service.create_comment() creates comment
          And: Code blocks are preserved exactly
          And: comment.is_solution flag is set correctly
    """
    # Arrange: Create approved thread
    thread = Thread(
        thread_id=uuid4(),
        author_id=test_agent.agent_id,
        title="How to use SQLAlchemy async?",
        body="Need help with async engine",
        tags=["python", "sqlalchemy"],
        error_log=None,
        environment=None,
        embedding=None,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.0,
    )

    # Save to DB
    thread_repo = SQLAlchemyThreadRepository(test_db)
    comment_repo = SQLAlchemyCommentRepository(test_db)
    thread_repo.add(thread)

    # Prepare answer with code blocks
    answer_content = """Use async engine:

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine("postgresql+asyncpg://...")
async with engine.begin() as conn:
    await conn.execute(text("SELECT 1"))
```

This enables async operations."""

    # Act: Create comment via REST API (same service layer as MCP)
    create_response = client.post(
        f"/v1/threads/{thread.thread_id}/comments",
        headers={"X-API-Key": "sk-agentbook-test-key"},
        json={"content": answer_content, "is_solution": True},
    )

    # Assert: Verify response
    assert create_response.status_code == 201
    result = create_response.json()
    comment_id = UUID(result["comment_id"])

    # Verify comment in database
    comment = comment_repo.get(comment_id)
    assert comment is not None
    assert comment.is_solution is True
    # Verify code blocks preserved
    assert "```python" in comment.content
    assert "create_async_engine" in comment.content
    assert "```" in comment.content


def test_mcp_answer_nested_reply(client: TestClient, test_db, test_agent) -> None:
    """Scenario: Nested reply to existing comment

    BDD Reference: Feature "answer_question MCP Tool"

    Given: Thread has approved comment
    When: Agent calls answer_question with parent_comment_id
    Then: service.create_comment() sets parent_id correctly
          And: Comment path reflects hierarchy (ltree)
    """
    # Arrange: Create thread and parent comment
    thread = Thread(
        thread_id=uuid4(),
        author_id=test_agent.agent_id,
        title="FastAPI middleware question",
        body="How to create custom middleware?",
        tags=["fastapi"],
        error_log=None,
        environment=None,
        embedding=None,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.0,
    )

    # Save to DB
    thread_repo = SQLAlchemyThreadRepository(test_db)
    comment_repo = SQLAlchemyCommentRepository(test_db)
    thread_repo.add(thread)

    # Create parent comment directly via service
    service = client.app.state.service
    parent = service.create_comment(
        thread_id=thread.thread_id,
        author_id=test_agent.agent_id,
        content="Use @app.middleware decorator",
        parent_id=None,
        is_solution=False,
    )

    # Act: Create nested reply
    create_response = client.post(
        f"/v1/threads/{thread.thread_id}/comments",
        headers={"X-API-Key": "sk-agentbook-test-key"},
        json={
            "content": "Alternative: use starlette.middleware directly",
            "parent_id": str(parent.comment_id),
            "is_solution": False,
        },
    )

    # Assert
    assert create_response.status_code == 201
    child_id = UUID(create_response.json()["comment_id"])

    # Verify parent_id and path
    child_comment = comment_repo.get(child_id)
    assert child_comment is not None
    assert child_comment.parent_id == parent.comment_id
    # Path should reflect ltree hierarchy
    assert child_comment.path.startswith(parent.path)


# ============================================================================
# Vote Answer Tool Tests
# ============================================================================


def test_mcp_vote_triggers_reward(client: TestClient, test_db, test_agent) -> None:
    """Scenario: Upvote triggers reward transaction

    BDD Reference: Feature "vote_answer MCP Tool"

    Given: Database has approved comment with author
          And: Voting agent has never voted on this comment
    When: Voting agent calls vote_answer with upvote
    Then: service.vote_comment() records the vote
          And: Response contains reward amount and updated wilson score
          And: Token transaction is created for comment author
    """
    # Create author agent
    author_agent = Agent(
        agent_id=uuid4(),
        api_key_hash="sk-agentbook-author-key-hash",
        model_type="author-model",
        token_balance=0,
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow(),
    )

    # Create thread and approved comment
    thread = Thread(
        thread_id=uuid4(),
        author_id=author_agent.agent_id,
        title="Test question",
        body="Test body",
        tags=["test"],
        error_log=None,
        environment=None,
        embedding=None,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.0,
    )

    comment_id = uuid4()
    comment = Comment(
        comment_id=comment_id,
        thread_id=thread.thread_id,
        author_id=author_agent.agent_id,
        content="Helpful answer",
        is_solution=True,
        parent_id=None,
        path=comment_id.hex,
        upvotes=0,
        downvotes=0,
        wilson_score=0.0,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.5,
    )

    # Save to DB
    agent_repo = SQLAlchemyAgentRepository(test_db)
    thread_repo = SQLAlchemyThreadRepository(test_db)
    comment_repo = SQLAlchemyCommentRepository(test_db)
    agent_repo.add(author_agent)
    thread_repo.add(thread)
    comment_repo.add(comment)

    # Act: Upvote via REST API
    vote_response = client.post(
        f"/v1/threads/comments/{comment.comment_id}/vote",
        headers={"X-API-Key": "sk-agentbook-test-key"},
        json={"vote_type": "upvote"},
    )

    # Assert
    assert vote_response.status_code == 200
    result = vote_response.json()
    assert "wilson_score" in result
    assert result["reward_issued"] > 0

    # Verify vote in database
    vote_repo = SQLAlchemyVoteRepository(test_db)
    vote = vote_repo.get(comment.comment_id, test_agent.agent_id)
    assert vote is not None
    assert vote.vote_type == "upvote"
    assert vote.voter_id == test_agent.agent_id

    # Verify token transaction
    tx_repo = SQLAlchemyTokenTransactionRepository(test_db)
    transactions = tx_repo.list_by_agent(author_agent.agent_id)
    assert any(tx.tx_type == "reward" and tx.amount == 5 for tx in transactions)


def test_mcp_vote_downvote_no_reward(client: TestClient, test_db, test_agent) -> None:
    """Scenario: Downvote improves answer quality signal

    BDD Reference: Feature "vote_answer MCP Tool"

    Given: Database has approved comment with author
    When: Voting agent calls vote_answer with downvote
    Then: service.vote_comment() records the vote
          And: NO token transaction is created (downvotes don't reward)
    """
    # Create author agent
    author_agent = Agent(
        agent_id=uuid4(),
        api_key_hash="sk-agentbook-author-key-hash",
        model_type="author-model",
        token_balance=0,
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow(),
    )

    # Create thread and approved comment
    thread = Thread(
        thread_id=uuid4(),
        author_id=author_agent.agent_id,
        title="Test question",
        body="Test body",
        tags=["test"],
        error_log=None,
        environment=None,
        embedding=None,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.0,
    )

    comment_id = uuid4()
    comment = Comment(
        comment_id=comment_id,
        thread_id=thread.thread_id,
        author_id=author_agent.agent_id,
        content="Incorrect answer",
        is_solution=True,
        parent_id=None,
        path=comment_id.hex,
        upvotes=0,
        downvotes=0,
        wilson_score=0.0,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=7.0,
    )

    # Save to DB
    agent_repo = SQLAlchemyAgentRepository(test_db)
    thread_repo = SQLAlchemyThreadRepository(test_db)
    comment_repo = SQLAlchemyCommentRepository(test_db)
    agent_repo.add(author_agent)
    thread_repo.add(thread)
    comment_repo.add(comment)

    # Act: Downvote
    vote_response = client.post(
        f"/v1/threads/comments/{comment.comment_id}/vote",
        headers={"X-API-Key": "sk-agentbook-test-key"},
        json={"vote_type": "downvote"},
    )

    # Assert
    assert vote_response.status_code == 200
    payload = vote_response.json()
    assert payload["reward_issued"] == 0
    assert payload["upvotes"] == 0
    assert payload["downvotes"] == 1

    # Verify author balance unchanged
    updated_author = agent_repo.get(author_agent.agent_id)
    assert updated_author is not None
    assert updated_author.token_balance == 0


def test_mcp_vote_duplicate_rejected(client: TestClient, test_db, test_agent) -> None:
    """Scenario: Duplicate vote is rejected

    BDD Reference: Feature "vote_answer MCP Tool"

    Given: Agent has already upvoted comment
    When: Agent calls vote_answer on same comment again
    Then: service.vote_comment() raises ConflictError
          And: API returns 409 Conflict with duplicate vote message
    """
    # Create author agent
    author_agent = Agent(
        agent_id=uuid4(),
        api_key_hash="sk-agentbook-author-key-hash",
        model_type="author-model",
        token_balance=0,
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow(),
    )

    # Create thread and approved comment
    thread = Thread(
        thread_id=uuid4(),
        author_id=author_agent.agent_id,
        title="Test question",
        body="Test body",
        tags=["test"],
        error_log=None,
        environment=None,
        embedding=None,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.0,
    )

    comment_id = uuid4()
    comment = Comment(
        comment_id=comment_id,
        thread_id=thread.thread_id,
        author_id=author_agent.agent_id,
        content="Helpful answer",
        is_solution=True,
        parent_id=None,
        path=comment_id.hex,
        upvotes=0,
        downvotes=0,
        wilson_score=0.0,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.5,
    )

    # Save to DB
    agent_repo = SQLAlchemyAgentRepository(test_db)
    thread_repo = SQLAlchemyThreadRepository(test_db)
    comment_repo = SQLAlchemyCommentRepository(test_db)
    agent_repo.add(author_agent)
    thread_repo.add(thread)
    comment_repo.add(comment)

    # First vote
    first_vote = client.post(
        f"/v1/threads/comments/{comment.comment_id}/vote",
        headers={"X-API-Key": "sk-agentbook-test-key"},
        json={"vote_type": "upvote"},
    )
    assert first_vote.status_code == 200

    # Act: Try duplicate vote
    duplicate_vote = client.post(
        f"/v1/threads/comments/{comment.comment_id}/vote",
        headers={"X-API-Key": "sk-agentbook-test-key"},
        json={"vote_type": "upvote"},
    )

    # Assert
    assert duplicate_vote.status_code == 409
    assert "already voted" in duplicate_vote.json()["detail"].lower()


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_mcp_authentication_error(client: TestClient) -> None:
    """Scenario: Authentication errors return 401

    BDD Reference: Feature "MCP Error Formatting"

    Given: FastAPI backend is running
    When: Agent sends request with invalid API key
    Then: API returns 401 Unauthorized
          And: Error message indicates authentication required
    """
    invalid_headers = {"X-API-Key": "ak-invalid-key-12345"}

    # Act
    response = client.get("/v1/threads", headers=invalid_headers)

    # Assert
    assert response.status_code == 401
    assert "Invalid API Key" in response.json()["detail"]


def test_mcp_not_found_error_thread(client: TestClient, test_db, test_agent) -> None:
    """Scenario: Not found errors indicate missing thread

    BDD Reference: Feature "MCP Error Formatting"

    Given: Agent has valid API key
    When: Agent references non-existent thread
    Then: service raises NotFoundError
          And: API returns 404 with error message
    """
    non_existent_id = uuid4()

    # Act: Try to get non-existent thread
    response = client.get(
        f"/v1/threads/{non_existent_id}",
        headers={"X-API-Key": "sk-agentbook-test-key"},
    )

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Thread not found"


def test_mcp_not_found_error_comment(client: TestClient, test_db, test_agent) -> None:
    """Scenario: Not found errors indicate missing comment

    BDD Reference: Feature "MCP Error Formatting"

    Given: Agent has valid API key
    When: Agent references non-existent comment for voting
    Then: service raises NotFoundError
          And: API returns 404 with error message
    """
    non_existent_id = uuid4()

    # Act: Try to vote on non-existent comment
    response = client.post(
        f"/v1/threads/comments/{non_existent_id}/vote",
        headers={"X-API-Key": "sk-agentbook-test-key"},
        json={"vote_type": "upvote"},
    )

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Comment not found"


def test_mcp_validation_error_invalid_vote_type(
    client: TestClient, test_db, test_agent
) -> None:
    """Scenario: Validation errors for invalid parameters

    BDD Reference: Feature "MCP Error Formatting"

    Given: Agent has valid API key
    And: Thread has approved comment
    When: Agent sends invalid vote_type parameter
    Then: Validation error is returned with 422 status
    """
    # Create thread and comment
    thread = Thread(
        thread_id=uuid4(),
        author_id=test_agent.agent_id,
        title="Test question",
        body="Test body",
        tags=["test"],
        error_log=None,
        environment=None,
        embedding=None,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.0,
    )

    comment_id = uuid4()
    comment = Comment(
        comment_id=comment_id,
        thread_id=thread.thread_id,
        author_id=test_agent.agent_id,
        content="Answer",
        is_solution=True,
        parent_id=None,
        path=comment_id.hex,
        upvotes=0,
        downvotes=0,
        wilson_score=0.0,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.0,
    )

    # Save to DB
    thread_repo = SQLAlchemyThreadRepository(test_db)
    comment_repo = SQLAlchemyCommentRepository(test_db)
    thread_repo.add(thread)
    comment_repo.add(comment)

    # Act: Try invalid vote_type
    response = client.post(
        f"/v1/threads/comments/{comment.comment_id}/vote",
        headers={"X-API-Key": "sk-agentbook-test-key"},
        json={"vote_type": "star"},
    )

    # Assert
    assert response.status_code == 422
    assert "vote_type" in response.json()["detail"][0]["loc"]


# ============================================================================
# End-to-End Workflow Tests
# ============================================================================


def test_mcp_e2e_search_ask_answer_vote_workflow(client: TestClient, test_db) -> None:
    """Scenario: Search -> Ask -> Answer -> Vote workflow

    BDD Reference: Feature "Multi-Step Agent Workflow via MCP"

    Given: Three agents with valid API keys (questioner, answerer, voter)
          And: SSE connection is established at /mcp/sse
    When: Questioner performs search_agentbook (returns empty)
          And: Questioner performs ask_question
          And: Answerer performs answer_question on the thread
          And: Voter performs vote_answer with upvote
    Then: All 4 MCP tool calls succeed (via REST API proxy)
          And: Token reward is issued to answer author
          And: Wilson score is updated on answer
    """
    # Arrange: Create three agents
    questioner = Agent(
        agent_id=uuid4(),
        api_key_hash="sk-agentbook-questioner-key-hash",
        model_type="claude",
        token_balance=100,
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow(),
    )

    answerer = Agent(
        agent_id=uuid4(),
        api_key_hash="sk-agentbook-answerer-key-hash",
        model_type="gemini",
        token_balance=100,
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow(),
    )

    voter = Agent(
        agent_id=uuid4(),
        api_key_hash="sk-agentbook-voter-key-hash",
        model_type="cursor",
        token_balance=100,
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow(),
    )

    # Save agents to DB
    agent_repo = SQLAlchemyAgentRepository(test_db)
    thread_repo = SQLAlchemyThreadRepository(test_db)
    comment_repo = SQLAlchemyCommentRepository(test_db)
    tx_repo = SQLAlchemyTokenTransactionRepository(test_db)

    agent_repo.add(questioner)
    agent_repo.add(answerer)
    agent_repo.add(voter)

    # Step 1: Search returns empty results
    search_response = client.get(
        "/v1/search",
        headers={"X-API-Key": "sk-agentbook-questioner-key"},
        params={"query": "Redis timeout connection issue", "limit": 5},
    )
    assert search_response.status_code == 200
    assert search_response.json()["total"] == 0

    # Step 2: Ask question
    ask_response = client.post(
        "/v1/threads",
        headers={"X-API-Key": "sk-agentbook-questioner-key"},
        json={
            "title": "Redis timeout fix",
            "body": "Getting connection timeout after 30s when connecting from FastAPI",
            "tags": ["fastapi", "redis"],
            "error_log": "TimeoutError: Redis connection timeout",
        },
    )
    assert ask_response.status_code == 201
    thread_id = UUID(ask_response.json()["thread_id"])

    # Approve thread for answering
    thread = thread_repo.get(thread_id)
    thread.review_status = "approved"
    thread.review_score = 8.0
    thread.reviewed_at = datetime.utcnow()
    thread_repo.add(thread)

    # Step 3: Answer question
    answer_response = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers={"X-API-Key": "sk-agentbook-answerer-key"},
        json={
            "content": """Set socket_timeout in Redis:

```python
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    socket_timeout=60,
    socket_connect_timeout=10
)
```

Also add retry logic for resilience.""",
            "is_solution": True,
        },
    )
    assert answer_response.status_code == 201
    comment_id = UUID(answer_response.json()["comment_id"])

    # Approve comment for voting
    comment = comment_repo.get(comment_id)
    comment.review_status = "approved"
    comment.review_score = 8.0
    comment.reviewed_at = datetime.utcnow()
    comment_repo.add(comment)

    # Step 4: Vote on answer
    vote_response = client.post(
        f"/v1/threads/comments/{comment_id}/vote",
        headers={"X-API-Key": "sk-agentbook-voter-key"},
        json={"vote_type": "upvote"},
    )
    assert vote_response.status_code == 200
    vote_payload = vote_response.json()

    # Verify token reward
    assert vote_payload["reward_issued"] > 0
    assert "wilson_score" in str(vote_payload)

    # Verify answerer earned tokens
    updated_answerer = agent_repo.get(answerer.agent_id)
    assert updated_answerer is not None
    assert updated_answerer.token_balance > 100

    # Verify token transaction
    transactions = tx_repo.list_by_agent(answerer.agent_id)
    assert any(tx.tx_type == "reward" and tx.amount > 0 for tx in transactions)

    # Verify answer content preserved (code blocks)
    updated_comment = comment_repo.get(comment_id)
    assert updated_comment is not None
    assert "```python" in updated_comment.content
    assert "socket_timeout" in updated_comment.content


def test_mcp_e2e_search_finds_existing_solution(
    client: TestClient, test_db, test_agent
) -> None:
    """Scenario: Search finds existing solution, no question needed

    BDD Reference: Feature "Multi-Step Agent Workflow via MCP"

    Given: Database has approved question with high-quality solution
    When: Agent performs search_agentbook for similar problem
    Then: Search returns relevant results with high similarity
          And: Agent can implement solution from search results
    """
    # Arrange: Create existing question with solution
    thread = Thread(
        thread_id=uuid4(),
        author_id=test_agent.agent_id,
        title="Python import error: No module named 'fastmcp'",
        body="Getting ModuleNotFoundError when trying to import fastmcp",
        tags=["python", "mcp"],
        error_log="ModuleNotFoundError: No module named 'fastmcp'",
        environment=None,
        embedding=None,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.5,
    )

    comment_id = uuid4()
    comment = Comment(
        comment_id=comment_id,
        thread_id=thread.thread_id,
        author_id=test_agent.agent_id,
        content='Install using: `pip install "mcp[cli]"`',
        is_solution=True,
        parent_id=None,
        path=comment_id.hex,
        upvotes=5,
        downvotes=0,
        wilson_score=0.72,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=9.0,
    )

    # Save to DB
    thread_repo = SQLAlchemyThreadRepository(test_db)
    comment_repo = SQLAlchemyCommentRepository(test_db)
    thread_repo.add(thread)
    comment_repo.add(comment)

    # Act: Search for similar problem
    search_response = client.get(
        "/v1/search",
        headers={"X-API-Key": "sk-agentbook-test-key"},
        params={"query": "fastmcp module not found", "limit": 5},
    )

    # Assert
    assert search_response.status_code == 200
    payload = search_response.json()
    assert payload["total"] == 1
    result = payload["results"][0]

    assert "fastmcp" in result["title"]
    assert result["similarity_score"] > 0
    assert result["top_solution"] is not None
    assert "pip install" in result["top_solution"]["content_preview"]
