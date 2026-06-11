"""Verifies features/exact-duplicate-friction.feature.

An exact error_signature duplicate (the only tier earning similarity 1.0) is
refused at write time with improve-mode guidance instead of being created
alongside an advisory. Lower tiers keep the admit-and-advise contract pinned
by test_write_dedup.py.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.presentation.mcp.tools import handle_contribute
from backend.tests.conftest import _build_contract_service

SIG = "RuntimeError: Event loop is closed"


def _build():
    service, ctx = _build_contract_service()
    prior = service.create_problem(
        author_id=ctx["author"].agent_id,
        description="asyncpg connection raises on interpreter shutdown after loop close",
        error_signature=SIG,
    )
    return service, ctx, prior


# Scenario: exact duplicate refused (service contract)


def test_contribute_with_exact_signature_duplicate_is_refused_and_not_persisted():
    service, ctx, prior = _build()
    before = len(ctx["problems"].list_all())

    result = service.contribute(
        author_id=ctx["author"].agent_id,
        description="Another service hits the closed event loop on teardown",
        error_signature=SIG,
        solution_content="Close the pool before the loop shuts down",
    )

    assert result["status"] == "duplicate_problem"
    assert result["problem_id"] is None
    rows = result["existing_problems"]
    assert rows and rows[0]["match_quality"] == "exact"
    assert str(prior.problem_id) in [r["problem_id"] for r in rows]
    assert "improve" in result["advice"].lower()
    assert len(ctx["problems"].list_all()) == before


# Scenario: exact duplicate refused over REST with 409


def test_post_problems_with_exact_signature_duplicate_returns_409():
    from backend.application.security import generate_api_key, hash_api_key
    from backend.domain.models import Agent
    from backend.main import create_app
    from backend.presentation.api.deps import get_service

    service, ctx, prior = _build()
    key = generate_api_key()
    ctx["agents"].add(
        Agent(api_key_hash=hash_api_key(key), model_type="test", agent_id=uuid4())
    )
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/v1/problems",
        json={
            "description": "Another service hits the closed event loop on teardown",
            "error_signature": SIG,
        },
        headers={"Authorization": f"Bearer {key}"},
    )

    assert response.status_code == 409, response.text
    body = response.json()["error"]
    assert body["code"] == "duplicate_problem"
    assert str(prior.problem_id) in body["message"]
    assert body["details"][0]["match_quality"] == "exact"


# Scenario: transport parity over MCP remember


@pytest.mark.asyncio
async def test_mcp_remember_exact_duplicate_returns_duplicate_problem_error():
    service = MagicMock()
    service.contribute.return_value = {
        "status": "duplicate_problem",
        "problem_id": None,
        "solution_id": None,
        "existing_problems": [
            {
                "problem_id": str(uuid4()),
                "match_quality": "exact",
                "similarity_score": 1.0,
                "description_preview": "asyncpg connection raises on shutdown",
            }
        ],
        "advice": "An identical problem already exists.",
    }

    result = await handle_contribute(
        service,
        uuid4(),
        {
            "description": "Another service hits the closed event loop",
            "error_signature": SIG,
        },
    )

    data = json.loads(result[0]["text"])
    assert data["error"] == "duplicate_problem"
    assert data["existing_problems"][0]["match_quality"] == "exact"


# Scenario: paraphrase without the exact signature is still created with advisory


def test_paraphrase_with_different_signature_is_created_with_advisory():
    # A signature that is neither a substring nor a superstring of the
    # prior's stays below the "exact" tier, so admit-and-advise applies.
    service, ctx, prior = _build()

    result = service.contribute(
        author_id=ctx["author"].agent_id,
        description="asyncpg connection raises on interpreter shutdown after loop close",
        error_signature="RuntimeError: cannot schedule new futures after shutdown",
    )

    assert result["status"] in ("similar_exists", "problem_created")
    assert result["problem_id"] is not None
    assert ctx["problems"].get(UUID(result["problem_id"])) is not None


# Scenario: novel problem unaffected


def test_novel_problem_is_created_with_empty_advisory():
    service, ctx, _ = _build()

    result = service.contribute(
        author_id=ctx["author"].agent_id,
        description="Tailwind JIT purge strips dynamically composed class names",
        error_signature="UnknownAtRule: @apply unknown utility",
    )

    assert result["status"] in ("problem_created", "knowledge_created")
    assert not (result.get("existing_problems") or [])
