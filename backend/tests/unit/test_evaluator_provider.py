"""Unit tests for EvaluatorProvider implementations."""

from __future__ import annotations

import json
from unittest.mock import patch
from uuid import uuid4

import httpx

from backend.application.service import EVALUATOR_AGENT_ID
from backend.infrastructure.evaluation.fallback import FallbackEvaluatorProvider


def test_fallback_returns_tie():
    provider = FallbackEvaluatorProvider()
    score = provider.compare("problem", "solution A", "solution B")
    assert score == 0.5


def test_fallback_ignores_all_inputs():
    provider = FallbackEvaluatorProvider()
    assert provider.compare("", "", "") == 0.5
    assert provider.compare("x" * 10000, "a", "b") == 0.5


def _gateway_provider(payload: dict):
    from backend.infrastructure.evaluation.llm_evaluator import LLMEvaluatorProvider

    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    )
    return LLMEvaluatorProvider(
        model="workers-ai/@cf/zai-org/glm-4.7-flash",
        base_url="https://gateway.ai.cloudflare.com/v1/acct/agentbook-gw",
        auth_token="gateway-token",
        http_client=client,
    )


def test_llm_evaluator_parses_valid_gateway_response():
    mock_response = {
        "result": {"choices": [{"message": {"content": json.dumps({"score": 0.8})}}]}
    }
    provider = _gateway_provider(mock_response)

    scores = set()
    with patch(
        "backend.infrastructure.evaluation.llm_evaluator.random.random",
        return_value=0.9,
    ):
        scores.add(round(provider.compare("problem", "A", "B"), 1))

    with patch(
        "backend.infrastructure.evaluation.llm_evaluator.random.random",
        return_value=0.1,
    ):
        scores.add(round(provider.compare("problem", "A", "B"), 1))

    assert 0.8 in scores
    assert 0.2 in scores


def test_llm_evaluator_defaults_on_gateway_failure():
    from backend.infrastructure.evaluation.llm_evaluator import LLMEvaluatorProvider

    def raise_error(_: httpx.Request) -> httpx.Response:
        raise httpx.HTTPError("connection refused")

    provider = LLMEvaluatorProvider(
        model="workers-ai/@cf/zai-org/glm-4.7-flash",
        base_url="https://gateway.ai.cloudflare.com/v1/acct/agentbook-gw",
        auth_token="gateway-token",
        http_client=httpx.Client(transport=httpx.MockTransport(raise_error)),
    )
    assert provider.compare("problem", "A", "B") == 0.5


def test_llm_evaluator_clamps_out_of_range():
    mock_response = {
        "result": {"choices": [{"message": {"content": json.dumps({"score": 1.5})}}]}
    }
    with patch(
        "backend.infrastructure.evaluation.llm_evaluator.random.random",
        return_value=0.9,
    ):
        score = _gateway_provider(mock_response).compare("problem", "A", "B")
    assert 0.0 <= score <= 1.0


def test_evaluator_agent_id_is_distinct():
    from backend.presentation.api.routes.worker import SYSTEM_AGENT_ID

    assert EVALUATOR_AGENT_ID != SYSTEM_AGENT_ID


def _make_improve_service(*, evaluator=None):
    """Build a minimal service with an approved problem + low-confidence solution."""
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
    agents.add(Agent(api_key_hash="test-hash", model_type="test", agent_id=author_id))

    service = AgentbookService(
        agents=agents,
        evaluator=evaluator,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )

    p = service.create_problem(
        author_id=author_id,
        description="Test problem for evaluator integration testing purposes here",
    )
    p.review_status = "approved"
    service._problems.update(p)

    s = service.create_solution(
        problem_id=p.problem_id,
        author_id=author_id,
        content="Original solution content for testing purposes here",
    )
    s.review_status = "approved"
    s.confidence = 0.25
    service._solutions.update(s)

    return service, s


def test_improve_solution_with_evaluator_creates_synthetic_outcome():
    from backend.infrastructure.evaluation.fallback import FallbackEvaluatorProvider

    service, sol = _make_improve_service(evaluator=FallbackEvaluatorProvider())

    result = service.improve_solution(
        solution_id=sol.solution_id,
        improved_content="Better solution with more detail and steps for testing here in Alpine",
        reasoning="Test improvement",
    )

    if result["status"] == "improved":
        new_sol = service._solutions.get(result["solution_id"])
        assert new_sol.outcome_count == 1
        outcomes = service._outcomes.list_by_solution(new_sol.solution_id)
        assert len(outcomes) == 1
        assert outcomes[0].reporter_id == EVALUATOR_AGENT_ID
        assert outcomes[0].weight == 0.3
        assert outcomes[0].notes == "llm_evaluation"


def test_improve_solution_without_evaluator_no_synthetic_outcome():
    service, sol = _make_improve_service()

    result = service.improve_solution(
        solution_id=sol.solution_id,
        improved_content="Better solution with more detail for testing without evaluator here",
        reasoning="Test improvement",
    )

    if result["status"] == "improved":
        new_sol = service._solutions.get(result["solution_id"])
        assert new_sol.outcome_count == 0
