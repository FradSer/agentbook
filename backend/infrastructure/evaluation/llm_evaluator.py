from __future__ import annotations

import json
import logging
import random

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a solution quality evaluator. Given a problem description and two "
    "candidate solutions (A and B), determine which solution better solves the "
    "problem. Consider correctness, completeness, actionability, and clarity.\n\n"
    'Respond with ONLY a JSON object: {"score": <float>}\n'
    "where score is 0.0-1.0 indicating how much better B is than A.\n"
    "> 0.5 means B is better, < 0.5 means A is better, 0.5 means equal."
)


class LLMEvaluatorProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    def compare(
        self,
        problem_description: str,
        solution_a: str,
        solution_b: str,
    ) -> float:
        # Randomize presentation order to eliminate position bias.
        swapped = random.random() < 0.5
        if swapped:
            first, second = solution_b, solution_a
        else:
            first, second = solution_a, solution_b

        user_prompt = (
            f"## Problem\n{problem_description}\n\n"
            f"## Solution A\n{first}\n\n"
            f"## Solution B\n{second}"
        )

        try:
            response = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.0,
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            score = json.loads(content)["score"]
            score = max(0.0, min(1.0, float(score)))
        except Exception:
            logger.warning("LLM evaluation failed, defaulting to 0.5", exc_info=True)
            return 0.5

        # If we swapped presentation order, invert the score.
        if swapped:
            score = 1.0 - score

        return score


def resolve_evaluator_provider() -> LLMEvaluatorProvider | None:
    api_key = settings.openrouter_api_key
    if not api_key:
        return None
    return LLMEvaluatorProvider(
        api_key=api_key,
        model=settings.evaluator_model,
    )
