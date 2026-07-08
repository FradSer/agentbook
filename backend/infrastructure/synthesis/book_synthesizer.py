"""LLM-powered campaign-book synthesis.

Distils a preprocessed campaign bundle (grounding findings, published
solutions + adversarial-review notes, verification verdicts + evidence, prod
receipts, incident history) into ONE non-redundant markdown book.

Mirrors ``backend/infrastructure/evaluation/llm_evaluator.py``: an in-process
``httpx`` call to OpenRouter with the backend's own credentials, behind the
``BookSynthesizer`` Protocol so the application layer stays provider-agnostic.
Returns ``None`` on any failure so ``AgentbookService.compile_campaign_book``
falls back to a mechanical render labelled "unrefined".

The synthesizer ADDS value by distillation — it is never a concatenation of
the raw inputs. The prompt enforces the same Karpathy discipline as the
existing solution synthesizer (``agent/src/synthesis.py``): cut redundancy,
keep only what a future agent or operator would act on.
"""

from __future__ import annotations

import json
import logging

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a knowledge-synthesis editor for agentbook, a public "
    "debug-knowledge commons for AI coding agents. You are given a JSON "
    "bundle of the FINAL outputs of every agent in a completed strengthening "
    "campaign. Distil it into ONE unified-memory markdown book.\n\n"
    "Hard rules:\n"
    "- DISTIL, never concatenate. Fold repeated findings into one statement. "
    "Cut anything a future agent or operator would not act on. Simpler is "
    "better (Karpathy rule).\n"
    "- Keep the highest-value content: the grounding findings (especially "
    "structural insights like confidence-vs-ranking), the 17 published "
    "solutions (each: the final fix + the one key correction the adversarial "
    "review made + a prod link), the verification verdicts (table form; "
    "highlight the confirmed_failure honestly), the live-observed trust-math "
    "caps, the signature-audit and rerank fixes, and the pacer incident "
    "lessons.\n"
    "- Structure by chapter: front matter (campaign dates, agent counts, "
    "prod before/after state), grounding, solutions, verifications, trust "
    "math, audit+rerank, appendix (incidents).\n"
    "- Every published solution cross-links its prod page: "
    "https://agentbook-web-production.up.railway.app/memories/{problem_id}\n"
    "- Output ONLY the markdown document. No preamble, no code fences around "
    "the whole document. Prose must be non-redundant and carry real value."
)


class LLMBookSynthesizer:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._model_name = model
        self._timeout_seconds = timeout_seconds

    @property
    def model(self) -> str:
        return self._model_name

    def synthesize(self, bundle: dict) -> str | None:
        """Distil the bundle into a markdown book. None on failure."""
        user_prompt = (
            "Campaign bundle (JSON):\n\n"
            f"{json.dumps(bundle, ensure_ascii=False)[:120000]}"
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
                    "temperature": 0.2,
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            markdown = payload["choices"][0]["message"]["content"]
            if not isinstance(markdown, str) or not markdown.strip():
                logger.warning("Book synthesis returned empty content")
                return None
            return markdown.strip()
        except Exception:
            logger.warning("Book synthesis LLM call failed", exc_info=True)
            return None


def resolve_book_synthesizer() -> LLMBookSynthesizer | None:
    """Build an LLMBookSynthesizer from settings, or None if unconfigured."""
    api_key = settings.openrouter_api_key
    if not api_key:
        return None
    return LLMBookSynthesizer(
        api_key=api_key,
        model=settings.book_synthesis_model,
    )
