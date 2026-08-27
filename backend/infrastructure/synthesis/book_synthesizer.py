"""LLM-powered campaign-book synthesis.

Distils a preprocessed campaign bundle (grounding findings, published
solutions + adversarial-review notes, verification verdicts + evidence, prod
receipts, incident history) into ONE non-redundant markdown book.

Calls the Cloudflare AI Gateway through ``httpx``, behind the
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
_DEFAULT_GATEWAY_MODEL = "workers-ai/@cf/zai-org/glm-4.7-flash"

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
        model: str,
        timeout_seconds: float = 120.0,
        *,
        base_url: str | None = None,
        auth_token: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        if base_url is None:
            raise ValueError("LLMBookSynthesizer requires an AI Gateway URL")
        if not auth_token:
            raise ValueError("gateway auth token is required")
        self._url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            + base_url.rstrip("/").split("/")[-2]
            + "/ai/run"
        )
        self._headers = {
            "Authorization": f"Bearer {auth_token}",
            "cf-aig-gateway-id": settings.ai_gateway_id,
            "Content-Type": "application/json",
        }
        self._model_name = model
        self._timeout_seconds = timeout_seconds
        self._http = http_client

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
            request = {
                "model": self._model_name,
                "input": {
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 8192,
                    "temperature": 0.2,
                },
            }
            client = self._http or httpx.Client(timeout=self._timeout_seconds)
            response = client.post(self._url, headers=self._headers, json=request)
            response.raise_for_status()
            payload = response.json()
            result = payload.get("result") or payload
            choices = result.get("choices") or []
            message = choices[0]["message"]
            markdown = message.get("content") or message.get("reasoning") or ""
            if not isinstance(markdown, str) or not markdown.strip():
                logger.warning("Book synthesis returned empty content")
                return None
            return markdown.strip()
        except Exception:
            logger.warning("Book synthesis LLM call failed", exc_info=True)
            return None


def resolve_book_synthesizer() -> LLMBookSynthesizer | None:
    """Build the Cloudflare Workers AI Gateway book synthesizer."""
    if not settings.ai_gateway_base_url or not settings.ai_gateway_auth_token:
        return None
    model = settings.book_synthesis_model
    if not model.startswith("workers-ai/"):
        model = _DEFAULT_GATEWAY_MODEL
    return LLMBookSynthesizer(
        model=model,
        base_url=settings.ai_gateway_base_url,
        auth_token=settings.ai_gateway_auth_token,
    )
