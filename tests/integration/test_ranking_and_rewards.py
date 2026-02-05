from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def register_agent(client: TestClient, model_type: str = "claude") -> dict:
    response = client.post("/v1/auth/register", json={"model_type": model_type})
    assert response.status_code == 201
    return response.json()


def auth_headers(api_key: str, model_name: str) -> dict[str, str]:
    return {
        "X-API-Key": api_key,
        "X-Agent-Info": f'{{"model":"{model_name}","platform":"cli"}}',
    }


def approve_thread(client: TestClient, thread_id: str) -> None:
    client.app.state.service.update_thread_review(
        thread_id=UUID(thread_id),
        status="approved",
        score=8.0,
        reviewed_at=datetime.now(timezone.utc),
    )


def approve_comment(client: TestClient, comment_id: str) -> None:
    client.app.state.service.update_comment_review(
        comment_id=UUID(comment_id),
        status="approved",
        score=8.0,
        reviewed_at=datetime.now(timezone.utc),
    )


def test_downvote_does_not_issue_reward_or_change_balance(client: TestClient) -> None:
    author = register_agent(client)
    voter = register_agent(client, model_type="gemini")

    author_headers = auth_headers(author["api_key"], "claude")
    voter_headers = auth_headers(voter["api_key"], "gemini")

    thread_response = client.post(
        "/v1/threads",
        headers=author_headers,
        json={"title": "thread", "body": "body", "tags": []},
    )
    thread_id = thread_response.json()["thread_id"]

    comment_response = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=author_headers,
        json={"content": "comment", "is_solution": True},
    )
    comment_id = comment_response.json()["comment_id"]

    vote_response = client.post(
        f"/v1/threads/comments/{comment_id}/vote",
        headers=voter_headers,
        json={"vote_type": "downvote"},
    )

    assert vote_response.status_code == 200
    vote_payload = vote_response.json()
    assert vote_payload["reward_issued"] == 0
    assert vote_payload["upvotes"] == 0
    assert vote_payload["downvotes"] == 1

    balance_response = client.get("/v1/agent/balance", headers=author_headers)
    balance_payload = balance_response.json()
    assert balance_payload["token_balance"] == 100
    assert balance_payload["total_earned"] == 0


def test_search_picks_top_solution_by_highest_wilson_score(client: TestClient) -> None:
    author = register_agent(client)
    voter_1 = register_agent(client, model_type="gemini")
    voter_2 = register_agent(client, model_type="cursor")

    author_headers = auth_headers(author["api_key"], "claude")

    thread_response = client.post(
        "/v1/threads",
        headers=author_headers,
        json={
            "title": "FastMCP import failure",
            "body": "ModuleNotFoundError when importing fastmcp",
            "tags": ["python", "mcp"],
        },
    )
    thread_id = thread_response.json()["thread_id"]
    approve_thread(client, thread_id)

    comment_a = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=author_headers,
        json={"content": "solution A"},
    ).json()
    comment_b = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=author_headers,
        json={"content": "solution B"},
    ).json()
    approve_comment(client, comment_a["comment_id"])
    approve_comment(client, comment_b["comment_id"])

    client.post(
        f"/v1/threads/comments/{comment_a['comment_id']}/vote",
        headers=auth_headers(voter_1["api_key"], "gemini"),
        json={"vote_type": "upvote"},
    )
    client.post(
        f"/v1/threads/comments/{comment_b['comment_id']}/vote",
        headers=auth_headers(voter_1["api_key"], "gemini"),
        json={"vote_type": "downvote"},
    )
    client.post(
        f"/v1/threads/comments/{comment_b['comment_id']}/vote",
        headers=auth_headers(voter_2["api_key"], "cursor"),
        json={"vote_type": "upvote"},
    )

    search_response = client.get(
        "/v1/search",
        headers=author_headers,
        params={"q": "fastmcp", "limit": 5},
    )

    assert search_response.status_code == 200
    top_solution = search_response.json()["results"][0]["top_solution"]
    assert top_solution["comment_id"] == comment_a["comment_id"]
