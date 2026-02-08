"""Integration tests for MCP SSE transport.

These tests validate MCP protocol over Server-Sent Events (SSE).
Requires RUN_DOCKER_TESTS=1 for real PostgreSQL.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.mark.smoke
def test_sse_connection_established() -> None:
    """Test that SSE connection can be established at /mcp/sse.

    Expected to fail initially with 404 Not Found until endpoint is implemented.
    """
    app = create_app()
    client = TestClient(app)

    # Attempt to connect to SSE endpoint
    with client.stream("GET", "/mcp/sse") as response:
        assert response.status_code == 200, "SSE endpoint should return 200 OK"
        assert response.headers["content-type"].startswith("text/event-stream"), \
            "SSE endpoint should return text/event-stream content type"
        assert response.headers.get("cache-control") == "no-cache", \
            "SSE should disable caching"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_vote_triggers_reward(test_api_client, test_db) -> None:
    """Test vote_answer tool triggers token reward transaction.

    BDD Reference: Scenario "Upvote triggers reward transaction"

    Given: Database has approved comment "comment-5"
          And agent "agent-111" has never voted on comment-5
    When: Agent sends vote_answer MCP tool call with upvote
    Then: MCP tool calls service.vote_comment
          And response contains reward amount and wilson score
    """
    import json
    from datetime import datetime
    from uuid import uuid4

    from app.domain.models import Agent, Comment, Thread

    # Create author agent
    author = Agent(
        agent_id=uuid4(),
        api_key_hash="hash-author",
        model_type="author-model",
        token_balance=0,
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow(),
    )

    # Create voter agent
    voter = Agent(
        agent_id=uuid4(),
        api_key_hash="hash-of-test-key",
        model_type="voter-model",
        token_balance=100,
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow(),
    )

    thread = Thread(
        thread_id=uuid4(),
        author_id=author.agent_id,
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

    comment = Comment(
        comment_id=uuid4(),
        thread_id=thread.thread_id,
        author_id=author.agent_id,
        content="Helpful answer",
        is_solution=True,
        parent_id=None,
        path="",
        upvotes=0,
        downvotes=0,
        wilson_score=0.0,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.5,
    )

    # Save to DB
    from app.infrastructure.persistence.sqlalchemy_repositories import (
        SQLAlchemyAgentRepository,
        SQLAlchemyCommentRepository,
        SQLAlchemyThreadRepository,
        SQLAlchemyTokenTransactionRepository,
        SQLAlchemyVoteRepository,
    )

    agent_repo = SQLAlchemyAgentRepository(test_db)
    thread_repo = SQLAlchemyThreadRepository(test_db)
    comment_repo = SQLAlchemyCommentRepository(test_db)

    agent_repo.add(author)
    agent_repo.add(voter)
    thread_repo.add(thread)
    comment_repo.add(comment)

    headers = {"X-API-Key": "sk-test-valid-key", "Accept": "text/event-stream"}

    mcp_request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "vote_answer",
            "arguments": {"comment_id": str(comment.comment_id), "vote_type": "upvote"},
        },
    }

    # Act
    async with test_api_client.stream("POST", "/mcp/sse", headers=headers) as response:
        # Send MCP request (SSE send logic placeholder)
        # Note: Actual SSE protocol implementation needed

        # Read response
        result = None
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if data.get("id") == 5 and "result" in data:
                    result = data["result"]
                    break

        # Assert
        assert result is not None
        text = result["content"][0]["text"]
        assert "Vote recorded successfully" in text
        assert "Reward Issued: 5 tokens" in text
        assert "Wilson Score:" in text

        # Verify vote in database
        vote_repo = SQLAlchemyVoteRepository(test_db)
        votes = await vote_repo.list_by_comment(comment.comment_id)
        assert len(votes) == 1
        assert votes[0].vote_type == "upvote"
        assert votes[0].voter_id == voter.agent_id

        # Verify token transaction
        tx_repo = SQLAlchemyTokenTransactionRepository(test_db)
        transactions = await tx_repo.list_by_agent(author.agent_id)
        assert any(tx.tx_type == "reward" and tx.amount == 5 for tx in transactions)


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_answer_preserves_markdown(test_api_client, test_db) -> None:
    """Test answer_question tool preserves Markdown code blocks.

    BDD Reference: Scenario "Submit answer with code blocks via MCP"

    Given: Database has approved question "thread-3"
          And agent has valid API key "sk-abc"
    When: Agent sends answer_question with code blocks
    Then: MCP tool calls service.create_comment
          And code blocks are preserved exactly
          And comment is created successfully
    """
    import json
    from datetime import datetime
    from uuid import uuid4

    from app.domain.models import Agent, Thread

    # Arrange: Create test agent
    agent = Agent(
        agent_id=uuid4(),
        api_key_hash="hash-of-test-key",
        model_type="test-model",
        token_balance=100,
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow(),
    )

    # Create and approve thread
    thread = Thread(
        thread_id=uuid4(),
        author_id=agent.agent_id,
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
    from app.infrastructure.persistence.sqlalchemy_repositories import (
        SQLAlchemyAgentRepository,
        SQLAlchemyCommentRepository,
        SQLAlchemyThreadRepository,
    )

    agent_repo = SQLAlchemyAgentRepository(test_db)
    thread_repo = SQLAlchemyThreadRepository(test_db)
    comment_repo = SQLAlchemyCommentRepository(test_db)

    agent_repo.add(agent)
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

    headers = {"X-API-Key": "sk-test-valid-key", "Accept": "text/event-stream"}

    mcp_request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "answer_question",
            "arguments": {
                "thread_id": str(thread.thread_id),
                "content": answer_content,
                "is_solution": True,
            },
        },
    }

    # Act: Send MCP request via SSE
    async with test_api_client.stream("POST", "/mcp/sse", headers=headers) as response:
        # Read SSE response
        result = None
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if data.get("id") == 4 and "result" in data:
                    result = data["result"]
                    break

        # Assert: Verify response
        assert result is not None
        text = result["content"][0]["text"]
        assert "Answer submitted successfully" in text
        assert "Comment ID:" in text

        # Extract comment ID from response
        import re

        comment_id_match = re.search(r"Comment ID: ([0-9a-f-]{36})", text)
        assert comment_id_match is not None
        comment_id = uuid4(comment_id_match.group(1))

        # Verify comment in database
        comment = comment_repo.get(comment_id)
        assert comment is not None
        assert comment.is_solution is True
        # Verify code blocks preserved
        assert "```python" in comment.content
        assert "create_async_engine" in comment.content
        assert "```" in comment.content


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_search_returns_formatted_results(test_api_client, test_db) -> None:
    """Test search_agentbook tool returns formatted Markdown results.

    BDD Reference: Scenario "Successful search returns formatted Markdown"

    Given: Database has approved question with thread_id "thread-1"
           - title: "ModuleNotFoundError fix"
           - tags: ["python"]
           - similarity: 0.92
           And thread-1 has approved answer with wilson_score 0.85
    When: Agent calls search_agentbook via MCP
    Then: Response contains formatted Markdown with similarity and wilson scores
    """
    import json
    from datetime import datetime
    from uuid import uuid4

    from app.domain.models import Agent, Comment, Thread

    # Arrange: Create test data
    agent = Agent(
        agent_id=uuid4(),
        api_key_hash="hash-of-test-key",
        model_type="test-model",
        token_balance=100,
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow(),
    )

    thread = Thread(
        thread_id=uuid4(),
        author_id=agent.agent_id,
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

    comment = Comment(
        comment_id=uuid4(),
        thread_id=thread.thread_id,
        author_id=agent.agent_id,
        content="Install the package: `pip install module-name`",
        is_solution=True,
        parent_id=None,
        path="",
        upvotes=10,
        downvotes=1,
        wilson_score=0.85,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=9.0,
    )

    # Save to DB
    from app.infrastructure.persistence.sqlalchemy_repositories import (
        SQLAlchemyAgentRepository,
        SQLAlchemyCommentRepository,
        SQLAlchemyThreadRepository,
    )

    agent_repo = SQLAlchemyAgentRepository(test_db)
    thread_repo = SQLAlchemyThreadRepository(test_db)
    comment_repo = SQLAlchemyCommentRepository(test_db)

    agent_repo.add(agent)
    thread_repo.add(thread)
    comment_repo.add(comment)

    # Act: Call search_agentbook via MCP
    headers = {"X-API-Key": "sk-test-valid-key", "Accept": "text/event-stream"}

    mcp_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "search_agentbook", "arguments": {"query": "import error", "limit": 3}},
    }

    async with test_api_client.stream("POST", "/mcp/sse", headers=headers) as response:
        # Send tool call (implementation depends on MCP SDK)
        # ... send mcp_request via SSE ...

        # Read response
        result = None
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if data.get("id") == 1 and "result" in data:
                    result = data["result"]
                    break

        # Assert: Verify Markdown formatting
        assert result is not None
        assert "content" in result
        assert len(result["content"]) > 0

        text = result["content"][0]["text"]
        assert "# Search Results" in text
        assert "ModuleNotFoundError fix" in text
        assert "0.92" in text or "Similarity" in text
        assert "wilson" in text.lower() or "0.85" in text
