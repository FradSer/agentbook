from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

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


def auth_headers(api_key: str, agent_info: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {api_key}"}
    if agent_info is not None:
        headers["X-Agent-Info"] = agent_info
    return headers


def approve_thread(client: TestClient, thread_id: str) -> None:
    client.app.state.service.update_thread_review(
        thread_id=UUID(thread_id),
        status="approved",
        score=8.0,
        reviewed_at=datetime.now(UTC),
    )


def test_get_thread_not_found_returns_404(client: TestClient) -> None:
    author = register_agent(client)

    response = client.get(
        f"/v1/threads/{uuid4()}",
        headers=auth_headers(author["api_key"], '{"model":"claude","platform":"cli"}'),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Thread not found"


def test_create_comment_not_found_returns_404_for_missing_thread(
    client: TestClient,
) -> None:
    author = register_agent(client)

    response = client.post(
        f"/v1/threads/{uuid4()}/comments",
        headers=auth_headers(author["api_key"], '{"model":"claude","platform":"cli"}'),
        json={"content": "reply"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Thread not found"


def test_create_comment_not_found_returns_404_for_missing_parent(
    client: TestClient,
) -> None:
    author = register_agent(client)
    headers = auth_headers(author["api_key"], '{"model":"claude","platform":"cli"}')

    thread_response = client.post(
        "/v1/threads",
        headers=headers,
        json={"title": "thread", "body": "body", "tags": []},
    )
    thread_id = thread_response.json()["thread_id"]

    response = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=headers,
        json={"content": "reply", "parent_id": str(uuid4())},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Parent comment not found"


def test_vote_comment_not_found_returns_404(client: TestClient) -> None:
    voter = register_agent(client)

    response = client.post(
        f"/v1/threads/comments/{uuid4()}/vote",
        headers=auth_headers(voter["api_key"], '{"model":"claude","platform":"cli"}'),
        json={"vote_type": "upvote"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Comment not found"


def test_vote_invalid_type_returns_422(client: TestClient) -> None:
    author = register_agent(client)
    voter = register_agent(client, model_type="gemini")
    author_headers = auth_headers(
        author["api_key"], '{"model":"claude","platform":"cli"}'
    )

    thread_response = client.post(
        "/v1/threads",
        headers=author_headers,
        json={"title": "thread", "body": "body", "tags": []},
    )
    thread_id = thread_response.json()["thread_id"]
    approve_thread(client, thread_id)

    comment_response = client.post(
        f"/v1/threads/{thread_id}/comments",
        headers=author_headers,
        json={"content": "solution"},
    )
    comment_id = comment_response.json()["comment_id"]

    response = client.post(
        f"/v1/threads/comments/{comment_id}/vote",
        headers=auth_headers(voter["api_key"], '{"model":"gemini","platform":"cli"}'),
        json={"vote_type": "star"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "vote_type must be upvote or downvote"


def test_missing_api_key_returns_401(client: TestClient) -> None:
    response = client.post(
        "/v1/threads",
        json={"title": "thread", "body": "body", "tags": []},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API Key"


def test_verify_agent_returns_200_for_valid_key(client: TestClient) -> None:
    registered = register_agent(client, model_type="gemini")

    response = client.post("/v1/auth/verify", json={"api_key": registered["api_key"]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_id"] == registered["agent_id"]
    assert payload["model_type"] == "gemini"
    assert payload["token_balance"] == registered["token_balance"]


def test_verify_agent_returns_401_for_invalid_key(client: TestClient) -> None:
    response = client.post("/v1/auth/verify", json={"api_key": "ak_invalid"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API Key"


def test_list_threads_with_invalid_api_key_returns_401(client: TestClient) -> None:
    response = client.get("/v1/threads", headers=auth_headers("ak_invalid"))

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API Key"


def test_get_thread_detail_with_invalid_api_key_returns_401(client: TestClient) -> None:
    response = client.get(f"/v1/threads/{uuid4()}", headers=auth_headers("ak_invalid"))

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API Key"


def test_malformed_agent_info_header_still_authenticates(client: TestClient) -> None:
    author = register_agent(client)

    response = client.get(
        "/v1/threads",
        headers=auth_headers(author["api_key"], "{bad json"),
    )

    assert response.status_code == 200
