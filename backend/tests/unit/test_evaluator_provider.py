"""Unit tests for EvaluatorProvider implementations."""

from __future__ import annotations

import json
from unittest.mock import patch
from uuid import uuid4

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


def test_llm_evaluator_parses_valid_response():
    from backend.infrastructure.evaluation.llm_evaluator import LLMEvaluatorProvider

    mock_response = {"choices": [{"message": {"content": json.dumps({"score": 0.8})}}]}

    with patch("backend.infrastructure.evaluation.llm_evaluator.httpx.post") as mock:
        mock.return_value.status_code = 200
        mock.return_value.raise_for_status = lambda: None
        mock.return_value.json.return_value = mock_response

        provider = LLMEvaluatorProvider(api_key="test", model="test-model")

        # Run enough times to test both swap orders
        scores = set()
        with patch(
            "backend.infrastructure.evaluation.llm_evaluator.random.random",
            return_value=0.9,
        ):
            score = provider.compare("problem", "A", "B")
            scores.add(round(score, 1))

        with patch(
            "backend.infrastructure.evaluation.llm_evaluator.random.random",
            return_value=0.1,
        ):
            score = provider.compare("problem", "A", "B")
            scores.add(round(score, 1))

        # When not swapped (random > 0.5): score = 0.8 (B better)
        # When swapped (random < 0.5): score = 1.0 - 0.8 = 0.2 (A better after inversion)
        assert 0.8 in scores
        assert 0.2 in scores


def test_llm_evaluator_defaults_on_failure():
    from backend.infrastructure.evaluation.llm_evaluator import LLMEvaluatorProvider

    with patch("backend.infrastructure.evaluation.llm_evaluator.httpx.post") as mock:
        mock.side_effect = Exception("connection refused")

        provider = LLMEvaluatorProvider(api_key="test", model="test-model")
        score = provider.compare("problem", "A", "B")

    assert score == 0.5


def test_llm_evaluator_clamps_out_of_range():
    from backend.infrastructure.evaluation.llm_evaluator import LLMEvaluatorProvider

    mock_response = {"choices": [{"message": {"content": json.dumps({"score": 1.5})}}]}

    with (
        patch("backend.infrastructure.evaluation.llm_evaluator.httpx.post") as mock,
        patch(
            "backend.infrastructure.evaluation.llm_evaluator.random.random",
            return_value=0.9,
        ),
    ):
        mock.return_value.status_code = 200
        mock.return_value.raise_for_status = lambda: None
        mock.return_value.json.return_value = mock_response

        provider = LLMEvaluatorProvider(api_key="test", model="test-model")
        score = provider.compare("problem", "A", "B")

    assert 0.0 <= score <= 1.0


def test_evaluator_agent_id_is_distinct():
    from agent.src.synthesis import SYSTEM_AGENT_ID

    assert EVALUATOR_AGENT_ID != SYSTEM_AGENT_ID


def test_improve_solution_with_evaluator_creates_synthetic_outcome():
    from backend.application.service import AgentbookService
    from backend.domain.models import Agent
    from backend.infrastructure.evaluation.fallback import FallbackEvaluatorProvider
    from backend.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
        InMemoryTokenTransactionRepository,
    )

    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(
        Agent(
            api_key_hash="test-hash",
            model_type="test",
            token_balance=100,
            agent_id=author_id,
        )
    )

    # FallbackEvaluatorProvider returns 0.5 (tie), so no synthetic outcome
    # should change success/failure counts in a meaningful way.
    service = AgentbookService(
        agents=agents,
        transactions=InMemoryTokenTransactionRepository(),
        evaluator=FallbackEvaluatorProvider(),
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

    result = service.improve_solution(
        solution_id=s.solution_id,
        improved_content="Better solution with more detail and steps for testing here in Alpine",
        reasoning="Test improvement",
    )

    if result["status"] == "improved":
        # Verify synthetic outcome was created
        new_sol = service._solutions.get(result["solution_id"])
        assert new_sol.outcome_count == 1  # synthetic outcome
        outcomes = service._outcomes.list_by_solution(new_sol.solution_id)
        assert len(outcomes) == 1
        assert outcomes[0].reporter_id == EVALUATOR_AGENT_ID
        assert outcomes[0].weight == 0.3
        assert outcomes[0].notes == "llm_evaluation"


def test_improve_solution_without_evaluator_no_synthetic_outcome():
    from backend.application.service import AgentbookService
    from backend.domain.models import Agent
    from backend.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
        InMemoryTokenTransactionRepository,
    )

    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(
        Agent(
            api_key_hash="test-hash",
            model_type="test",
            token_balance=100,
            agent_id=author_id,
        )
    )

    # No evaluator passed
    service = AgentbookService(
        agents=agents,
        transactions=InMemoryTokenTransactionRepository(),
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )

    p = service.create_problem(
        author_id=author_id,
        description="Test problem without evaluator for regression testing purposes",
    )
    p.review_status = "approved"
    service._problems.update(p)

    s = service.create_solution(
        problem_id=p.problem_id,
        author_id=author_id,
        content="Original solution for testing without evaluator purposes here",
    )
    s.review_status = "approved"
    s.confidence = 0.25
    service._solutions.update(s)

    result = service.improve_solution(
        solution_id=s.solution_id,
        improved_content="Better solution with more detail for testing without evaluator here",
        reasoning="Test improvement",
    )

    if result["status"] == "improved":
        new_sol = service._solutions.get(result["solution_id"])
        assert new_sol.outcome_count == 0  # no synthetic outcome
