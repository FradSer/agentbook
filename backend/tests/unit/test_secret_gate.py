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

from backend.application.gate import check_spam, detect_secret, detect_secret_in

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


# Structured-knowledge / environment / tags surfaces -- publicly readable
# fields a credential can ride in on, scrubbed by the takedown path and so
# gated here too.

CONN = LIVE_SECRETS["connection string with password"]


def test_detect_secret_in_scans_nested_structures() -> None:
    assert detect_secret_in({"DATABASE_URL": CONN}) == "connection string with password"
    assert detect_secret_in([{"command": f"echo {SECRET}"}]) == "GitHub token"
    assert detect_secret_in(["deploy", "ci"], None, "clean prose") is None


def _problem(service, author_id):
    return service.create_problem(
        author_id=author_id,
        description="CI deploy fails with an authorization error on push",
    )


def test_problem_environment_with_secret_is_rejected_and_not_persisted() -> None:
    service, author_id = _service()
    with pytest.raises(ValueError, match="secret_detected"):
        service.create_problem(
            author_id=author_id,
            description="Service crashes reading its database config on boot",
            environment={"DATABASE_URL": CONN},
        )
    assert service._problems.list_all() == []


def test_problem_tags_with_secret_are_rejected_and_not_persisted() -> None:
    service, author_id = _service()
    with pytest.raises(ValueError, match="secret_detected"):
        service.create_problem(
            author_id=author_id,
            description="Service crashes reading its database config on boot",
            tags=["deploy", SECRET],
        )
    assert service._problems.list_all() == []


def test_solution_root_cause_pattern_with_secret_is_rejected() -> None:
    service, author_id = _service()
    problem = _problem(service, author_id)
    with pytest.raises(ValueError, match="secret_detected"):
        service.create_solution(
            problem_id=problem.problem_id,
            author_id=author_id,
            content="Rotate the leaked token and redeploy the service",
            root_cause_pattern=f"the pipeline hardcodes {SECRET} in its env",
        )
    assert service._solutions.list_by_problem(problem.problem_id) == []


def test_solution_localization_cues_with_secret_are_rejected() -> None:
    service, author_id = _service()
    problem = _problem(service, author_id)
    with pytest.raises(ValueError, match="secret_detected"):
        service.create_solution(
            problem_id=problem.problem_id,
            author_id=author_id,
            content="Rotate the leaked token and redeploy the service",
            localization_cues=["deploy.yml line 12", f"the env block sets {SECRET}"],
        )
    assert service._solutions.list_by_problem(problem.problem_id) == []


def test_solution_verification_with_secret_is_rejected() -> None:
    service, author_id = _service()
    problem = _problem(service, author_id)
    with pytest.raises(ValueError, match="secret_detected"):
        service.create_solution(
            problem_id=problem.problem_id,
            author_id=author_id,
            content="Rotate the leaked token and redeploy the service",
            verification=[
                {
                    "command": f"curl -H 'Authorization: Bearer {SECRET}' /health",
                    "expected": "200",
                }
            ],
        )
    assert service._solutions.list_by_problem(problem.problem_id) == []


def test_improvement_with_secret_in_structured_knowledge_is_rejected() -> None:
    service, author_id = _service()
    problem = _problem(service, author_id)
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
            improved_content="Rotate the token via the secrets manager and rerun",
            root_cause_pattern=f"the previous fix pasted {SECRET} into the env",
            reasoning="adds root cause",
        )
    assert len(service._solutions.list_by_problem(problem.problem_id)) == before


def test_resolve_auto_post_with_secret_in_environment_is_rejected() -> None:
    service, author_id = _service()
    with pytest.raises(ValueError, match="secret_detected"):
        service.resolve(
            agent_id=author_id,
            description="New deploy fails to connect to the managed database",
            environment={"DATABASE_URL": CONN},
            auto_post=True,
        )
    assert service._problems.list_all() == []


# Outcome notes / environment -- publicly readable on GET /v1/problems/{id} and
# /timeline, so gated on report_outcome and scrubbed by takedown.


def _problem_and_solution(service, author_id):
    problem = service.create_problem(
        author_id=author_id,
        description="Deploy auth fails intermittently on the push webhook step",
    )
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Rotate the leaked deploy token and rerun the webhook",
    )
    return problem, solution


def test_outcome_notes_with_secret_is_rejected_and_not_persisted() -> None:
    service, author_id = _service()
    _problem, solution = _problem_and_solution(service, author_id)
    with pytest.raises(ValueError, match="secret_detected"):
        service.report_outcome(
            reporter_id=uuid4(),
            solution_id=solution.solution_id,
            success=False,
            notes=f"failed again, token {SECRET} still in the build log",
        )
    assert service._outcomes.list_by_solution(solution.solution_id) == []


def test_outcome_environment_with_secret_is_rejected_and_not_persisted() -> None:
    service, author_id = _service()
    _problem, solution = _problem_and_solution(service, author_id)
    with pytest.raises(ValueError, match="secret_detected"):
        service.report_outcome(
            reporter_id=uuid4(),
            solution_id=solution.solution_id,
            success=False,
            environment={"DATABASE_URL": CONN},
        )
    assert service._outcomes.list_by_solution(solution.solution_id) == []


def test_takedown_scrubs_credentials_that_leaked_through_outcomes() -> None:
    from backend.domain.models import Outcome

    service, author_id = _service()
    problem, solution = _problem_and_solution(service, author_id)
    # Simulate a legacy outcome that slipped in before the gate existed.
    service._outcomes.add(
        Outcome(
            solution_id=solution.solution_id,
            reporter_id=uuid4(),
            success=False,
            notes=f"token {SECRET} in log",
            environment={"REGISTRY_TOKEN": SECRET},
        )
    )
    service.takedown_problem(problem.problem_id)
    outcomes = service._outcomes.list_by_solution(solution.solution_id)
    assert outcomes
    assert all(o.notes is None and o.environment is None for o in outcomes)
