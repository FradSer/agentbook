"""Async HTTP client for AgentBook REST API.

Simulates real external agent usage via httpx.
All operations return timing and result data for analysis.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class OperationResult:
    """Result of a single API operation."""

    operation: str
    status_code: int
    latency_seconds: float
    success: bool
    response_data: dict | None
    error: str | None


class AgentbookRESTClient:
    """Async HTTP client wrapping the AgentBook REST API."""

    def __init__(self, base_url: str, agent_label: str, client_ip: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.agent_label = agent_label
        self.client_ip = client_ip
        self.api_key: str | None = None
        self._client: httpx.AsyncClient | None = None
        self._latencies: list[float] = []

    async def __aenter__(self) -> AgentbookRESTClient:
        headers = {"User-Agent": f"sim-agent/{self.agent_label}"}
        # Present a distinct source IP so the server's per-IP rate limits
        # treat this simulated agent as its own external client, the way N
        # real agents on N machines would be — not N collapsed onto one.
        if self.client_ip:
            headers["X-Forwarded-For"] = self.client_ip
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0, connect=5.0),
            limits=httpx.Limits(max_connections=50),
            headers=headers,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> OperationResult:
        """Execute an HTTP request, capturing timing and result."""
        assert self._client is not None
        start = time.monotonic()
        try:
            response = await self._client.request(method, path, **kwargs)
            latency = time.monotonic() - start
            self._latencies.append(latency)
            try:
                data = response.json()
            except Exception:
                data = {"raw": response.text[:500]}
            success = 200 <= response.status_code < 300
            # Keep the parsed body regardless of status: every reader gates on
            # `success` already, and callers that re-classify a status (see
            # improve_solution) need the structured payload, not a string.
            return OperationResult(
                operation=f"{method} {path.split('?')[0]}",
                status_code=response.status_code,
                latency_seconds=latency,
                success=success,
                response_data=data,
                error=None if success else str(data),
            )
        except Exception as e:
            latency = time.monotonic() - start
            self._latencies.append(latency)
            return OperationResult(
                operation=f"{method} {path.split('?')[0]}",
                status_code=0,
                latency_seconds=latency,
                success=False,
                response_data=None,
                error=f"{type(e).__name__}: {e}",
            )

    # ── Auth ─────────────────────────────────────────────────────────

    async def register(self, model_type: str) -> OperationResult:
        result = await self._request(
            "POST", "/v1/auth/register", json={"model_type": model_type}
        )
        if result.success and result.response_data:
            self.api_key = result.response_data.get("api_key")
            # Carry the key on every subsequent request, reads included. An
            # authenticated read is keyed by agent id (300/minute) instead of
            # falling into the shared anonymous-IP budget (30/minute).
            if self.api_key and self._client is not None:
                self._client.headers["Authorization"] = f"Bearer {self.api_key}"
        return result

    async def verify(self) -> OperationResult:
        return await self._request(
            "POST", "/v1/auth/verify", json={"api_key": self.api_key}
        )

    # ── Search ───────────────────────────────────────────────────────

    async def search(
        self, query: str, limit: int = 10, include: str | None = None
    ) -> OperationResult:
        params: dict[str, Any] = {"q": query, "limit": limit}
        if include:
            params["include"] = include
        return await self._request("GET", "/v1/search", params=params)

    # ── Problems ─────────────────────────────────────────────────────

    async def list_problems(self, limit: int = 20) -> OperationResult:
        return await self._request("GET", "/v1/problems", params={"limit": limit})

    async def get_problem(self, problem_id: str) -> OperationResult:
        return await self._request("GET", f"/v1/problems/{problem_id}")

    async def get_timeline(self, problem_id: str) -> OperationResult:
        return await self._request("GET", f"/v1/problems/{problem_id}/timeline")

    async def create_problem(
        self,
        description: str,
        error_signature: str | None = None,
        tags: list[str] | None = None,
        environment: dict | None = None,
    ) -> OperationResult:
        body: dict[str, Any] = {"description": description}
        if error_signature:
            body["error_signature"] = error_signature
        if tags:
            body["tags"] = tags
        if environment:
            body["environment"] = environment
        return await self._request("POST", "/v1/problems", json=body)

    async def create_solution(
        self,
        problem_id: str,
        content: str,
        steps: list[str] | None = None,
    ) -> OperationResult:
        body: dict[str, Any] = {"content": content}
        if steps:
            body["steps"] = steps
        return await self._request(
            "POST",
            f"/v1/problems/{problem_id}/solutions",
            json=body,
        )

    # ── Solutions ────────────────────────────────────────────────────

    async def report_outcome(
        self,
        solution_id: str,
        success: bool,
        notes: str | None = None,
        environment: dict | None = None,
        time_saved_seconds: int | None = None,
    ) -> OperationResult:
        body: dict[str, Any] = {"success": success}
        if notes:
            body["notes"] = notes
        if environment:
            body["environment"] = environment
        if time_saved_seconds:
            body["time_saved_seconds"] = time_saved_seconds
        return await self._request(
            "POST",
            f"/v1/solutions/{solution_id}/outcomes",
            json=body,
        )

    async def improve_solution(
        self,
        solution_id: str,
        improved_content: str,
        improved_steps: list[str] | None = None,
        reasoning: str = "",
    ) -> OperationResult:
        body: dict[str, Any] = {
            "improved_content": improved_content,
            "reasoning": reasoning,
        }
        if improved_steps:
            body["improved_steps"] = improved_steps
        result = await self._request(
            "POST",
            f"/v1/solutions/{solution_id}/improve",
            json=body,
        )
        # A 409 from /improve is a gated rejection ("no_improvement"): the
        # proposal was evaluated correctly and saved for lineage, just not
        # promoted. That is a valid verdict the agent acts on, not an error.
        if result.status_code == 409:
            result.success = True
            result.error = None
        return result

    async def get_lineage(self, solution_id: str) -> OperationResult:
        return await self._request("GET", f"/v1/solutions/{solution_id}/lineage")

    # ── Dashboard ────────────────────────────────────────────────────

    async def get_radar(self) -> OperationResult:
        return await self._request("GET", "/v1/dashboard/radar")

    async def get_metrics(self) -> OperationResult:
        return await self._request("GET", "/v1/dashboard/metrics")

    async def get_usage(self) -> OperationResult:
        return await self._request("GET", "/v1/dashboard/usage")

    async def get_research_activity(self, memory_id: str) -> OperationResult:
        return await self._request(
            "GET", "/v1/research-activity", params={"memory_id": memory_id}
        )

    # ── Latency Stats ────────────────────────────────────────────────

    def get_latency_stats(self) -> dict[str, float]:
        if not self._latencies:
            return {
                "min": 0,
                "max": 0,
                "avg": 0,
                "p50": 0,
                "p95": 0,
                "p99": 0,
            }
        sorted_lat = sorted(self._latencies)
        n = len(sorted_lat)
        return {
            "min": sorted_lat[0],
            "max": sorted_lat[-1],
            "avg": sum(sorted_lat) / n,
            "p50": sorted_lat[int(n * 0.5)],
            "p95": sorted_lat[min(int(n * 0.95), n - 1)],
            "p99": sorted_lat[min(int(n * 0.99), n - 1)],
        }
