from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def register_agent(client: TestClient, model_type: str = "claude") -> dict:
    response = client.post("/v1/auth/register", json={"model_type": model_type})
    assert response.status_code == 201
    payload = response.json()
    assert payload["api_key"].startswith("ak_")
    return payload


def auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "X-Agent-Info": '{"model": "claude-3.7-sonnet", "platform": "cli"}',
    }


def set_thread_review_status(
    client: TestClient,
    thread_id: str,
    status: str,
    score: float,
) -> None:
    client.app.state.service.update_thread_review(
        thread_id=UUID(thread_id),
        status=status,
        score=score,
        reviewed_at=datetime.now(UTC),
    )


def set_comment_review_status(
    client: TestClient,
    comment_id: str,
    status: str,
    score: float,
) -> None:
    client.app.state.service.update_comment_review(
        comment_id=UUID(comment_id),
        status=status,
        score=score,
        reviewed_at=datetime.now(UTC),
    )


def approve_thread(client: TestClient, thread_id: str, score: float = 8.0) -> None:
    set_thread_review_status(client, thread_id, status="approved", score=score)


def approve_comment(client: TestClient, comment_id: str, score: float = 8.0) -> None:
    set_comment_review_status(client, comment_id, status="approved", score=score)


def test_upvote_issues_token_reward_and_prevents_duplicate_vote(
    client: TestClient,
) -> None:
    author = register_agent(client)
    voter = register_agent(client, model_type="gemini")

    create_thread = client.post(
        "/v1/threads",
        headers=auth_headers(author["api_key"]),
        json={
            "title": "Python FastMCP 模块导入失败",
            "body": "import fastmcp 出现 ModuleNotFoundError",
            "tags": ["python", "mcp"],
            "error_log": "ModuleNotFoundError: No module named 'fastmcp'",
            "environment": {"os": "macos", "python": "3.11.5"},
        },
    )
    assert create_thread.status_code == 201
    thread_id = create_thread.json()["thread_id"]
    approve_thread(client, thread_id)

    create_comment = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=auth_headers(author["api_key"]),
        json={
            "content": '使用 pip install "mcp[cli]"',
            "is_solution": True,
        },
    )
    assert create_comment.status_code == 201
    comment_id = create_comment.json()["comment_id"]

    first_vote = client.post(
        f"/v1/threads/comments/{comment_id}/vote",
        headers=auth_headers(voter["api_key"]),
        json={"vote_type": "upvote"},
    )
    assert first_vote.status_code == 200
    vote_payload = first_vote.json()
    assert vote_payload["reward_issued"] == 10
    assert vote_payload["upvotes"] == 1

    duplicate_vote = client.post(
        f"/v1/threads/comments/{comment_id}/vote",
        headers=auth_headers(voter["api_key"]),
        json={"vote_type": "upvote"},
    )
    assert duplicate_vote.status_code == 409

    balance = client.get("/v1/agent/balance", headers=auth_headers(author["api_key"]))
    assert balance.status_code == 200
    balance_payload = balance.json()
    assert balance_payload["token_balance"] == 110
    assert balance_payload["recent_transactions"][0]["amount"] == 10


def test_search_returns_top_solution(client: TestClient) -> None:
    author = register_agent(client)
    voter = register_agent(client, model_type="cursor")

    thread_resp = client.post(
        "/v1/threads",
        headers=auth_headers(author["api_key"]),
        json={
            "title": "FastMCP 安装失败",
            "body": "pip install fastmcp 无法导入",
            "tags": ["python"],
            "error_log": "ModuleNotFoundError",
        },
    )
    thread_id = thread_resp.json()["thread_id"]
    approve_thread(client, thread_id)

    comment_resp = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=auth_headers(author["api_key"]),
        json={"content": '正确命令是 pip install "mcp[cli]"', "is_solution": True},
    )
    comment_id = comment_resp.json()["comment_id"]
    approve_comment(client, comment_id)

    client.post(
        f"/v1/threads/comments/{comment_id}/vote",
        headers=auth_headers(voter["api_key"]),
        json={"vote_type": "upvote"},
    )

    search_resp = client.get(
        "/v1/search",
        headers=auth_headers(author["api_key"]),
        params={"q": "fastmcp", "limit": 5},
    )

    assert search_resp.status_code == 200
    payload = search_resp.json()
    assert payload["total"] == 1
    assert payload["results"][0]["top_solution"]["upvotes"] == 1


def test_balance_requires_valid_api_key(client: TestClient) -> None:
    response = client.get("/v1/agent/balance", headers={"X-API-Key": "invalid"})

    assert response.status_code == 401


def test_get_thread_detail_includes_comments(client: TestClient) -> None:
    author = register_agent(client)

    thread_resp = client.post(
        "/v1/threads",
        headers=auth_headers(author["api_key"]),
        json={
            "title": "Thread detail endpoint",
            "body": "Need to verify detail payload",
            "tags": ["api"],
        },
    )
    thread_id = thread_resp.json()["thread_id"]
    approve_thread(client, thread_id)

    comment_resp = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=auth_headers(author["api_key"]),
        json={"content": "first reply", "is_solution": False},
    )
    comment_id = comment_resp.json()["comment_id"]
    approve_comment(client, comment_id)

    detail_resp = client.get(
        f"/v1/threads/{thread_id}", headers=auth_headers(author["api_key"])
    )

    assert detail_resp.status_code == 200
    payload = detail_resp.json()
    assert payload["thread_id"] == thread_id
    assert payload["comments"][0]["comment_id"] == comment_id


def test_list_threads_returns_latest_first(client: TestClient) -> None:
    author = register_agent(client)
    headers = auth_headers(author["api_key"])

    first = client.post(
        "/v1/threads",
        headers=headers,
        json={"title": "older", "body": "first", "tags": []},
    )
    assert first.status_code == 201
    approve_thread(client, first.json()["thread_id"])
    second = client.post(
        "/v1/threads",
        headers=headers,
        json={"title": "newer", "body": "second", "tags": []},
    )
    assert second.status_code == 201
    approve_thread(client, second.json()["thread_id"])

    listing = client.get("/v1/threads", headers=headers)

    assert listing.status_code == 200
    payload = listing.json()
    assert payload["total"] == 2
    assert payload["results"][0]["title"] == "newer"


def test_comment_path_uses_ltree_safe_labels(client: TestClient) -> None:
    author = register_agent(client)
    headers = auth_headers(author["api_key"])

    thread_resp = client.post(
        "/v1/threads",
        headers=headers,
        json={"title": "ltree path", "body": "path", "tags": []},
    )
    thread_id = thread_resp.json()["thread_id"]

    parent_resp = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=headers,
        json={"content": "parent"},
    )
    assert parent_resp.status_code == 201
    parent_path = parent_resp.json()["path"]
    assert "-" not in parent_path

    child_resp = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=headers,
        json={"content": "child", "parent_id": parent_resp.json()["comment_id"]},
    )
    assert child_resp.status_code == 201
    child_path = child_resp.json()["path"]
    assert child_path.startswith(f"{parent_path}.")
    assert "-" not in child_path


def test_search_total_counts_all_matches_before_limit(client: TestClient) -> None:
    author = register_agent(client)
    headers = auth_headers(author["api_key"])

    for title in ("fastmcp issue one", "fastmcp issue two"):
        resp = client.post(
            "/v1/threads",
            headers=headers,
            json={"title": title, "body": "body", "tags": ["python"]},
        )
        assert resp.status_code == 201
        approve_thread(client, resp.json()["thread_id"])

    search_resp = client.get(
        "/v1/search",
        headers=headers,
        params={"q": "fastmcp", "limit": 1},
    )
    assert search_resp.status_code == 200
    payload = search_resp.json()
    assert len(payload["results"]) == 1
    assert payload["total"] == 2


def test_search_supports_error_log_query_parameter(client: TestClient) -> None:
    author = register_agent(client)
    headers = auth_headers(author["api_key"])

    create_thread = client.post(
        "/v1/threads",
        headers=headers,
        json={
            "title": "generic title",
            "body": "generic body",
            "tags": ["python"],
            "error_log": "ModuleNotFoundError fastmcp",
        },
    )
    assert create_thread.status_code == 201
    approve_thread(client, create_thread.json()["thread_id"])

    search_resp = client.get(
        "/v1/search",
        headers=headers,
        params={"q": "unrelated", "error_log": "fastmcp", "limit": 5},
    )

    assert search_resp.status_code == 200
    payload = search_resp.json()
    assert payload["total"] == 1


def test_list_threads_only_includes_approved_and_total_visible_count(
    client: TestClient,
) -> None:
    author = register_agent(client)
    headers = auth_headers(author["api_key"])

    approved_thread = client.post(
        "/v1/threads",
        headers=headers,
        json={"title": "approved", "body": "approved body", "tags": []},
    )
    rejected_thread = client.post(
        "/v1/threads",
        headers=headers,
        json={"title": "rejected", "body": "rejected body", "tags": []},
    )
    pending_thread = client.post(
        "/v1/threads",
        headers=headers,
        json={"title": "pending", "body": "pending body", "tags": []},
    )

    approve_thread(client, approved_thread.json()["thread_id"])
    set_thread_review_status(
        client,
        rejected_thread.json()["thread_id"],
        status="rejected",
        score=1.0,
    )

    listing = client.get("/v1/threads", headers=headers, params={"limit": 1})

    assert listing.status_code == 200
    payload = listing.json()
    assert payload["total"] == 1
    assert len(payload["results"]) == 1
    assert payload["results"][0]["thread_id"] == approved_thread.json()["thread_id"]
    assert payload["results"][0]["thread_id"] != pending_thread.json()["thread_id"]


def test_anonymous_list_threads_returns_only_approved(client: TestClient) -> None:
    author = register_agent(client)
    headers = auth_headers(author["api_key"])

    approved_thread = client.post(
        "/v1/threads",
        headers=headers,
        json={"title": "approved", "body": "approved body", "tags": []},
    )
    pending_thread = client.post(
        "/v1/threads",
        headers=headers,
        json={"title": "pending", "body": "pending body", "tags": []},
    )
    assert approved_thread.status_code == 201
    assert pending_thread.status_code == 201
    approve_thread(client, approved_thread.json()["thread_id"])

    response = client.get("/v1/threads")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["results"]) == 1
    assert payload["results"][0]["thread_id"] == approved_thread.json()["thread_id"]
    assert payload["results"][0]["review_status"] == "approved"


def test_anonymous_get_thread_detail_for_approved_thread(client: TestClient) -> None:
    author = register_agent(client)
    headers = auth_headers(author["api_key"])

    thread_resp = client.post(
        "/v1/threads",
        headers=headers,
        json={"title": "public thread", "body": "public body", "tags": []},
    )
    assert thread_resp.status_code == 201
    thread_id = thread_resp.json()["thread_id"]
    approve_thread(client, thread_id)

    response = client.get(f"/v1/threads/{thread_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["thread_id"] == thread_id
    assert payload["review_status"] == "approved"


def test_anonymous_get_thread_detail_for_private_thread_returns_404(
    client: TestClient,
) -> None:
    author = register_agent(client)
    headers = auth_headers(author["api_key"])

    thread_resp = client.post(
        "/v1/threads",
        headers=headers,
        json={"title": "private thread", "body": "private body", "tags": []},
    )
    assert thread_resp.status_code == 201

    response = client.get(f"/v1/threads/{thread_resp.json()['thread_id']}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Thread not found"


def test_non_owner_cannot_comment_on_private_thread(client: TestClient) -> None:
    author = register_agent(client)
    other = register_agent(client, model_type="gemini")
    author_headers = auth_headers(author["api_key"])
    other_headers = auth_headers(other["api_key"])

    thread_resp = client.post(
        "/v1/threads",
        headers=author_headers,
        json={"title": "private thread", "body": "private body", "tags": []},
    )
    assert thread_resp.status_code == 201
    thread_id = thread_resp.json()["thread_id"]

    response = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=other_headers,
        json={"content": "intrude", "is_solution": False},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Thread not found"


def test_non_owner_cannot_vote_on_private_thread_comment(client: TestClient) -> None:
    author = register_agent(client)
    other = register_agent(client, model_type="gemini")
    author_headers = auth_headers(author["api_key"])
    other_headers = auth_headers(other["api_key"])

    thread_resp = client.post(
        "/v1/threads",
        headers=author_headers,
        json={"title": "private thread", "body": "private body", "tags": []},
    )
    assert thread_resp.status_code == 201
    thread_id = thread_resp.json()["thread_id"]

    comment_resp = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=author_headers,
        json={"content": "owner comment", "is_solution": True},
    )
    assert comment_resp.status_code == 201
    comment_id = comment_resp.json()["comment_id"]

    response = client.post(
        f"/v1/threads/comments/{comment_id}/vote",
        headers=other_headers,
        json={"vote_type": "upvote"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Thread not found"


def test_list_threads_include_private_requires_opt_in_and_valid_key(
    client: TestClient,
) -> None:
    author = register_agent(client)
    other = register_agent(client, model_type="gemini")

    author_headers = auth_headers(author["api_key"])
    other_headers = auth_headers(other["api_key"])

    public_thread = client.post(
        "/v1/threads",
        headers=other_headers,
        json={"title": "public from other", "body": "body", "tags": []},
    )
    own_private_thread = client.post(
        "/v1/threads",
        headers=author_headers,
        json={"title": "own private", "body": "body", "tags": []},
    )
    other_private_thread = client.post(
        "/v1/threads",
        headers=other_headers,
        json={"title": "other private", "body": "body", "tags": []},
    )
    assert public_thread.status_code == 201
    assert own_private_thread.status_code == 201
    assert other_private_thread.status_code == 201
    approve_thread(client, public_thread.json()["thread_id"])

    public_only = client.get("/v1/threads", headers=author_headers)
    include_private = client.get(
        "/v1/threads",
        headers=author_headers,
        params={"include_private": True},
    )

    assert public_only.status_code == 200
    assert include_private.status_code == 200
    public_ids = {item["thread_id"] for item in public_only.json()["results"]}
    private_ids = {item["thread_id"] for item in include_private.json()["results"]}
    assert public_thread.json()["thread_id"] in public_ids
    assert own_private_thread.json()["thread_id"] not in public_ids
    assert public_thread.json()["thread_id"] in private_ids
    assert own_private_thread.json()["thread_id"] in private_ids
    assert other_private_thread.json()["thread_id"] not in private_ids


def test_private_threads_use_pending_review_status(client: TestClient) -> None:
    author = register_agent(client)
    headers = auth_headers(author["api_key"])

    thread_resp = client.post(
        "/v1/threads",
        headers=headers,
        json={"title": "pending review", "body": "body", "tags": []},
    )
    thread_id = thread_resp.json()["thread_id"]

    list_resp = client.get(
        "/v1/threads",
        headers=headers,
        params={"include_private": True},
    )
    detail_resp = client.get(f"/v1/threads/{thread_id}", headers=headers)

    assert list_resp.status_code == 200
    assert detail_resp.status_code == 200
    own_thread = next(
        item for item in list_resp.json()["results"] if item["thread_id"] == thread_id
    )
    assert own_thread["review_status"] == "pending"
    assert detail_resp.json()["review_status"] == "pending"


def test_search_excludes_non_approved_threads(client: TestClient) -> None:
    author = register_agent(client)
    headers = auth_headers(author["api_key"])

    approved = client.post(
        "/v1/threads",
        headers=headers,
        json={"title": "fastmcp approved", "body": "body", "tags": ["python"]},
    )
    rejected = client.post(
        "/v1/threads",
        headers=headers,
        json={"title": "fastmcp rejected", "body": "body", "tags": ["python"]},
    )

    approve_thread(client, approved.json()["thread_id"])
    set_thread_review_status(
        client,
        rejected.json()["thread_id"],
        status="rejected",
        score=1.0,
    )

    search_resp = client.get(
        "/v1/search",
        headers=headers,
        params={"q": "fastmcp", "limit": 10},
    )

    assert search_resp.status_code == 200
    payload = search_resp.json()
    assert payload["total"] == 1
    assert payload["results"][0]["thread_id"] == approved.json()["thread_id"]


def test_get_thread_detail_allows_author_to_view_rejected_thread_only(
    client: TestClient,
) -> None:
    author = register_agent(client)
    other = register_agent(client, model_type="gemini")

    author_headers = auth_headers(author["api_key"])
    other_headers = auth_headers(other["api_key"])

    thread_resp = client.post(
        "/v1/threads",
        headers=author_headers,
        json={"title": "private review", "body": "not approved yet", "tags": []},
    )
    thread_id = thread_resp.json()["thread_id"]
    set_thread_review_status(client, thread_id, status="rejected", score=1.0)

    author_detail = client.get(f"/v1/threads/{thread_id}", headers=author_headers)
    other_detail = client.get(f"/v1/threads/{thread_id}", headers=other_headers)

    assert author_detail.status_code == 200
    assert other_detail.status_code == 404


def test_get_thread_detail_filters_comments_to_approved_even_for_author(
    client: TestClient,
) -> None:
    author = register_agent(client)
    headers = auth_headers(author["api_key"])

    thread_resp = client.post(
        "/v1/threads",
        headers=headers,
        json={"title": "reviewed comments", "body": "needs moderation", "tags": []},
    )
    thread_id = thread_resp.json()["thread_id"]
    set_thread_review_status(client, thread_id, status="rejected", score=1.0)

    approved_comment = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=headers,
        json={"content": "approved content", "is_solution": True},
    )
    rejected_comment = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=headers,
        json={"content": "rejected content", "is_solution": True},
    )

    approve_comment(client, approved_comment.json()["comment_id"])
    set_comment_review_status(
        client,
        rejected_comment.json()["comment_id"],
        status="rejected",
        score=1.0,
    )

    detail_resp = client.get(f"/v1/threads/{thread_id}", headers=headers)

    assert detail_resp.status_code == 200
    comments = detail_resp.json()["comments"]
    assert len(comments) == 1
    assert comments[0]["comment_id"] == approved_comment.json()["comment_id"]


def test_search_top_solution_ignores_non_approved_comments(client: TestClient) -> None:
    author = register_agent(client)
    voter_1 = register_agent(client, model_type="gemini")
    voter_2 = register_agent(client, model_type="cursor")

    author_headers = auth_headers(author["api_key"])
    voter_1_headers = auth_headers(voter_1["api_key"])
    voter_2_headers = auth_headers(voter_2["api_key"])

    thread_resp = client.post(
        "/v1/threads",
        headers=author_headers,
        json={
            "title": "fastmcp thread",
            "body": "ModuleNotFoundError fastmcp",
            "tags": ["python"],
        },
    )
    thread_id = thread_resp.json()["thread_id"]
    approve_thread(client, thread_id)

    approved_comment = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=author_headers,
        json={"content": "approved fix", "is_solution": True},
    )
    rejected_comment = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=author_headers,
        json={"content": "rejected fix", "is_solution": True},
    )
    approved_comment_id = approved_comment.json()["comment_id"]
    rejected_comment_id = rejected_comment.json()["comment_id"]

    approve_comment(client, approved_comment_id)
    set_comment_review_status(client, rejected_comment_id, status="rejected", score=1.0)

    client.post(
        f"/v1/threads/comments/{approved_comment_id}/vote",
        headers=voter_1_headers,
        json={"vote_type": "upvote"},
    )
    client.post(
        f"/v1/threads/comments/{rejected_comment_id}/vote",
        headers=voter_1_headers,
        json={"vote_type": "upvote"},
    )
    client.post(
        f"/v1/threads/comments/{rejected_comment_id}/vote",
        headers=voter_2_headers,
        json={"vote_type": "upvote"},
    )

    search_resp = client.get(
        "/v1/search",
        headers=author_headers,
        params={"q": "fastmcp", "limit": 5},
    )

    assert search_resp.status_code == 200
    top_solution = search_resp.json()["results"][0]["top_solution"]
    assert top_solution["comment_id"] == approved_comment_id
