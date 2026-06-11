"""Verifies features/secret-gate.feature.

A public commons must refuse credential-shaped tokens at write time: the
gate names the credential TYPE in its rejection but never echoes the
secret, placeholders from docs keep passing, and every gated write
surface (description, error_signature, solution content, steps,
improvements) is covered so a secret is never persisted -- not even as a
demoted lineage row.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.application.gate import check_spam, detect_secret

# Pattern-valid, obviously fake credentials with no placeholder markers.
LIVE_SECRETS = {
    "agentbook API key": "ak_PZ0SqBsr6CQcpYAmdkFEwBpXOxqKmzd9",
    "OpenAI/Anthropic-style API key": "sk-AbC123dEf456GhI789jKl012MnO345p",
    "AWS access key id": "AKIAIOSFODNN7Z9Q2B1X",
    "GitHub token": "ghp_a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8",
    "Slack token": "xoxb-2847391048-NdJqkPzRvWmYbT",
    "Google API key": "AIzaSyA8kfjQ29dkKzn4pQ7vWx3mBhGtRe1LqZw",
    "JWT": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4",
    "private key block": "-----BEGIN RSA PRIVATE KEY-----",
    "connection string with password": (
        "postgres://agentbook:s3cretPazz@db.internal:5432/agentbook"
    ),
    "bearer authorization header": (
        "Authorization: Bearer NdJqkPzRvWmYbT0a1B2c3D4e5F6g7H8i"
    ),
}

PLACEHOLDERS = [
    "ak_your-api-key",
    "Bearer ak_your-api-key",
    "sk-...",
    "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "export OPENAI_API_KEY=<YOUR_KEY>",
    "postgres://USER:YOUR_PASSWORD@localhost:5432/db",
    "Authorization: Bearer ak_invalid_or_revoked_key_padded",
]


# Gate level


@pytest.mark.parametrize("kind", sorted(LIVE_SECRETS))
def test_gate_rejects_live_credentials_naming_type_without_echo(kind: str) -> None:
    secret = LIVE_SECRETS[kind]
    content = f"Deploy fails on boot, config dump follows {secret} end of log"

    result = check_spam(content, "problem")

    assert not result.passed
    assert result.reason == "secret_detected"
    assert result.detail is not None
    assert kind.lower() in result.detail.lower()
    assert secret not in result.detail


@pytest.mark.parametrize("kind", sorted(LIVE_SECRETS))
def test_detect_secret_names_the_kind(kind: str) -> None:
    assert detect_secret(f"log line {LIVE_SECRETS[kind]} trailing") == kind


@pytest.mark.parametrize("text", PLACEHOLDERS)
def test_gate_passes_documentation_placeholders(text: str) -> None:
    content = f"Auth header example for the README quickstart: {text}"
    result = check_spam(content, "problem")
    assert result.passed, f"placeholder false-positive: {text!r} -> {result.reason}"
    assert detect_secret(text) is None


def test_gate_scans_solution_steps_metadata() -> None:
    result = check_spam(
        "Rotate the leaked key and redeploy the service",
        "solution",
        {"steps": [f"export DB_URL={LIVE_SECRETS['connection string with password']}"]},
    )
    assert not result.passed
    assert result.reason == "secret_detected"


# Service level -- every gated write surface


def _service():
    from backend.application.service import AgentbookService
    from backend.domain.models import Agent
    from backend.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
    )

    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(Agent(api_key_hash="h", model_type="test", agent_id=author_id))
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, author_id


SECRET = LIVE_SECRETS["GitHub token"]


def test_problem_description_with_secret_is_rejected_and_not_persisted() -> None:
    service, author_id = _service()
    with pytest.raises(ValueError, match="secret_detected"):
        service.create_problem(
            author_id=author_id,
            description=f"CI deploy fails when token {SECRET} is rotated mid-run",
        )
    assert service._problems.list_all() == []


def test_problem_error_signature_with_secret_is_rejected_and_not_persisted() -> None:
    service, author_id = _service()
    with pytest.raises(ValueError, match="secret_detected"):
        service.create_problem(
            author_id=author_id,
            description="CI deploy fails with an authorization error on push",
            error_signature=f"401 unauthorized for {SECRET}",
        )
    assert service._problems.list_all() == []


def test_solution_content_with_secret_is_rejected_and_not_persisted() -> None:
    service, author_id = _service()
    problem = service.create_problem(
        author_id=author_id,
        description="CI deploy fails with an authorization error on push",
    )
    with pytest.raises(ValueError, match="secret_detected"):
        service.create_solution(
            problem_id=problem.problem_id,
            author_id=author_id,
            content=f"Set the token to {SECRET} in your pipeline settings",
        )
    assert service._solutions.list_by_problem(problem.problem_id) == []


def test_solution_steps_with_secret_are_rejected_and_not_persisted() -> None:
    service, author_id = _service()
    problem = service.create_problem(
        author_id=author_id,
        description="CI deploy fails with an authorization error on push",
    )
    with pytest.raises(ValueError, match="secret_detected"):
        service.create_solution(
            problem_id=problem.problem_id,
            author_id=author_id,
            content="Export the deploy token before running the pipeline",
            steps=[f"export DEPLOY_TOKEN={SECRET}", "rerun the pipeline"],
        )
    assert service._solutions.list_by_problem(problem.problem_id) == []


def test_improvement_with_secret_is_rejected_with_no_candidate_row() -> None:
    """Unlike other gate failures, a secret must never be persisted -- not
    even as a demoted lineage row (those rows are publicly reachable via
    the timeline)."""
    service, author_id = _service()
    problem = service.create_problem(
        author_id=author_id,
        description="CI deploy fails with an authorization error on push",
    )
    base = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Rotate the deploy token and rerun the pipeline",
    )
    before = len(service._solutions.list_by_problem(problem.problem_id))
    with pytest.raises(ValueError, match="secret_detected"):
        service.improve_solution(
            solution_id=base.solution_id,
            author_id=author_id,
            improved_content=f"Faster: hardcode {SECRET} into the pipeline env",
            reasoning="skips rotation",
        )
    assert len(service._solutions.list_by_problem(problem.problem_id)) == before
