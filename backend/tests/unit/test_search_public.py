"""Public-read REST search contract.

After the public-memory pivot, GET /v1/search must work without an
Authorization header. Writes (POST /v1/problems) still require auth.
"""

from __future__ import annotations

from backend.tests.conftest import _build_client


def test_search_returns_200_without_authorization_header():
    client, _ = _build_client()
    response = client.get("/v1/search", params={"q": "hydration error"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert "results" in body
    assert "total" in body


def test_search_returns_same_shape_with_and_without_auth():
    client, api_key = _build_client()

    anon = client.get("/v1/search", params={"q": "module not found"})
    auth = client.get(
        "/v1/search",
        params={"q": "module not found"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert anon.status_code == 200
    assert auth.status_code == 200
    assert set(anon.json().keys()) == set(auth.json().keys())


def test_post_problems_still_requires_authorization():
    client, _ = _build_client()
    response = client.post(
        "/v1/problems",
        json={
            "description": "ModuleNotFoundError importing numpy in Docker Alpine container"
        },
    )
    assert response.status_code == 401, response.text


def test_post_problems_succeeds_with_valid_authorization():
    client, api_key = _build_client()
    response = client.post(
        "/v1/problems",
        json={
            "description": "ModuleNotFoundError importing numpy in Docker Alpine container"
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert response.status_code in (200, 201), response.text
