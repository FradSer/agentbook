"""Cloudflare Workers AI reranking through the AI Gateway REST API."""

from __future__ import annotations

import httpx

from backend.core.config import settings
from backend.domain.services import RerankFn
from backend.infrastructure.reranking.noop import noop_rerank

_DEFAULT_MODEL = "@cf/baai/bge-reranker-base"
_DEFAULT_TIMEOUT_SECONDS = 5.0


class CloudflareReranker:
    """Rerank candidate documents with a Cloudflare-hosted model."""

    def __init__(
        self,
        *,
        model: str = _DEFAULT_MODEL,
        account_id: str | None = None,
        auth_token: str,
        gateway_id: str = "agentbook-gw",
        base_url: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not auth_token or not gateway_id:
            raise ValueError("Cloudflare AI Gateway credentials are required")
        if base_url:
            parts = base_url.rstrip("/").split("/")
            account_id = account_id or (parts[-2] if len(parts) >= 2 else "")
        if not account_id:
            raise ValueError("Cloudflare account id is required")
        self._url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run"
        self._model = model
        self._headers = {
            "Authorization": f"Bearer {auth_token}",
            "cf-aig-gateway-id": gateway_id,
            "Content-Type": "application/json",
        }
        self._http = http_client or httpx.Client(timeout=timeout_seconds)

    def __call__(self, query: str, candidates: list[str], top_k: int) -> list[int]:
        if not candidates:
            return []
        response = self._http.post(
            self._url,
            headers=self._headers,
            json={
                "model": self._model,
                "input": {
                    "query": query,
                    "contexts": [{"text": text} for text in candidates],
                    "top_k": min(top_k, len(candidates)),
                },
            },
        )
        response.raise_for_status()
        payload = response.json()
        rows = (payload.get("result") or {}).get("response") or []
        return [int(row["id"]) for row in rows]


def resolve_rerank_fn() -> RerankFn:
    if not settings.ai_gateway_base_url or not settings.ai_gateway_auth_token:
        return noop_rerank
    parts = settings.ai_gateway_base_url.rstrip("/").split("/")
    if len(parts) < 2:
        return noop_rerank
    account_id = parts[-2]
    return CloudflareReranker(
        account_id=account_id,
        auth_token=settings.ai_gateway_auth_token,
        gateway_id=settings.ai_gateway_id,
        base_url=settings.ai_gateway_base_url,
    )
