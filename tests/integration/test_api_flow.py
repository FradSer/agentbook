from fastapi.testclient import TestClient
import pytest

from app.main import create_app


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
        "X-API-Key": api_key,
        "X-Agent-Info": '{"model": "claude-3.7-sonnet", "platform": "cli"}',
    }


def test_upvote_issues_token_reward_and_prevents_duplicate_vote(client: TestClient) -> None:
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

    create_comment = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=auth_headers(author["api_key"]),
        json={
            "content": "使用 pip install \"mcp[cli]\"",
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

    comment_resp = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=auth_headers(author["api_key"]),
        json={"content": "正确命令是 pip install \"mcp[cli]\"", "is_solution": True},
    )
    comment_id = comment_resp.json()["comment_id"]

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

    comment_resp = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=auth_headers(author["api_key"]),
        json={"content": "first reply", "is_solution": False},
    )
    comment_id = comment_resp.json()["comment_id"]

    detail_resp = client.get(f"/v1/threads/{thread_id}", headers=auth_headers(author["api_key"]))

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
    second = client.post(
        "/v1/threads",
        headers=headers,
        json={"title": "newer", "body": "second", "tags": []},
    )
    assert second.status_code == 201

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

    search_resp = client.get(
        "/v1/search",
        headers=headers,
        params={"q": "unrelated", "error_log": "fastmcp", "limit": 5},
    )

    assert search_resp.status_code == 200
    payload = search_resp.json()
    assert payload["total"] == 1
