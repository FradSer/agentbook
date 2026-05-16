"""Adversarial deep-probe suite for the AgentBook REST API.

The persona-driven simulation exercises happy-path workflows. This module
attacks the REST surface with malformed, boundary, abusive, and injection
inputs and asserts the server degrades correctly: structured 4xx envelopes,
never a 500, never silent acceptance of invalid data.

Each probe declares the status codes it considers acceptable. A response is:
  - bug      : a 5xx, a transport failure, or a 2xx where input was invalid
  - anomaly  : a 4xx outside the expected family, or a missing error envelope
  - pass     : status within the expected set

Run standalone against an already-running backend:
    uv run python -m simulation.adversary --base-url http://127.0.0.1:8765
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from dataclasses import dataclass
from uuid import uuid4

import httpx

from simulation.problem_templates import (
    generate_improvement,
    generate_problem,
    generate_solution,
)

# Demo fixtures seeded by DEMO_MODE — real, resolvable resource IDs.
DEMO_PROBLEM_ID = "22222222-0000-0000-0000-000000000001"
DEMO_SOLUTION_ID = "33333333-0000-0000-1111-000000000001"

# Service-side cap on distinct outcome rows per reporter per hour
# (backend/application/service.py:_RATE_LIMIT).
_OUTCOME_RATE_LIMIT = 10

# Distinct synthetic source IPs so each probe group lands in its own
# per-IP rate-limit bucket (the server runs with proxy-header trust).
_IP_MAIN = "203.0.113.10"
_IP_SEARCH_FLOOD = "203.0.113.20"
_IP_REGISTER_FLOOD = "203.0.113.30"
_IP_OUTCOME_FLOOD = "203.0.113.40"
_IP_CONCURRENCY = "203.0.113.50"
# Per-agent IP prefix for the concurrency fleet (each agent its own /32).
_IP_FLEET_PREFIX = "198.51.100"


@dataclass
class ProbeResult:
    name: str
    category: str
    request: str
    status_code: int
    expected: list[int]
    verdict: str  # "pass" | "anomaly" | "bug"
    detail: str = ""


class AdversarialProbe:
    """Runs the adversarial probe suite against a base URL."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.results: list[ProbeResult] = []

    # ── Request helper ────────────────────────────────────────────────

    @staticmethod
    async def _send(
        client: httpx.AsyncClient,
        method: str,
        path: str,
        **kwargs: object,
    ) -> tuple[int, object, httpx.Headers]:
        try:
            resp = await client.request(method, path, **kwargs)  # type: ignore[arg-type]
            try:
                body: object = resp.json()
            except Exception:
                body = {"raw": resp.text[:300]}
            return resp.status_code, body, resp.headers
        except Exception as e:  # noqa: BLE001 - transport failure is a finding
            return 0, {"exception": f"{type(e).__name__}: {e}"}, httpx.Headers()

    def _record(
        self,
        *,
        name: str,
        category: str,
        request: str,
        status: int,
        expected: list[int],
        body: object,
        expect_rejection: bool,
    ) -> None:
        """Classify one probe response into pass / anomaly / bug."""
        detail = ""
        if status == 0:
            verdict = "bug"
            exc = body.get("exception") if isinstance(body, dict) else None
            detail = f"transport failure / no response ({exc})"
        elif status >= 500:
            verdict = "bug"
            detail = f"server error {status} — backend should never 5xx on input"
        elif expect_rejection and 200 <= status < 300:
            verdict = "bug"
            detail = f"invalid input was accepted ({status})"
        elif 400 <= status < 500 and not (
            isinstance(body, dict) and isinstance(body.get("error"), dict)
        ):
            verdict = "anomaly"
            detail = f"{status} response missing structured error envelope"
        elif status in expected:
            verdict = "pass"
        else:
            verdict = "anomaly"
            detail = f"unexpected status {status}, expected {expected}"
        self.results.append(
            ProbeResult(
                name=name,
                category=category,
                request=request,
                status_code=status,
                expected=expected,
                verdict=verdict,
                detail=detail,
            )
        )

    # ── Probe groups ──────────────────────────────────────────────────

    async def _probe_input_validation(
        self, client: httpx.AsyncClient, auth: dict[str, str]
    ) -> None:
        cat = "input_validation"
        long_text = "x" * 10_001
        cases: list[tuple[str, str, str, dict, list[int]]] = [
            ("desc_too_short", "POST", "/v1/problems", {"description": "short"}, [422]),
            ("desc_missing", "POST", "/v1/problems", {}, [422]),
            ("desc_wrong_type", "POST", "/v1/problems", {"description": 12345}, [422]),
            (
                "desc_too_long",
                "POST",
                "/v1/problems",
                {"description": long_text},
                [422],
            ),
            (
                "tags_too_many",
                "POST",
                "/v1/problems",
                {
                    "description": "A valid problem description that is long enough.",
                    "tags": [f"tag{i}" for i in range(25)],
                },
                [422],
            ),
        ]
        for name, method, path, payload, expected in cases:
            status, body, _ = await self._send(
                client, method, path, json=payload, headers=auth
            )
            self._record(
                name=name,
                category=cat,
                request=f"{method} {path}",
                status=status,
                expected=expected,
                body=body,
                expect_rejection=True,
            )

        # Solution / outcome / improve body validation.
        body_cases: list[tuple[str, str, dict]] = [
            (
                "solution_content_too_short",
                f"/v1/problems/{DEMO_PROBLEM_ID}/solutions",
                {"content": "tiny"},
            ),
            (
                "solution_steps_too_many",
                f"/v1/problems/{DEMO_PROBLEM_ID}/solutions",
                {
                    "content": "A valid solution body that clears the minimum.",
                    "steps": [f"step {i}" for i in range(60)],
                },
            ),
            (
                "outcome_success_missing",
                f"/v1/solutions/{DEMO_SOLUTION_ID}/outcomes",
                {"notes": "no success field"},
            ),
            (
                "outcome_success_non_bool",
                f"/v1/solutions/{DEMO_SOLUTION_ID}/outcomes",
                {"success": "maybe"},
            ),
            (
                "improve_content_too_short",
                f"/v1/solutions/{DEMO_SOLUTION_ID}/improve",
                {"improved_content": "no"},
            ),
        ]
        for name, path, payload in body_cases:
            status, body, _ = await self._send(
                client, "POST", path, json=payload, headers=auth
            )
            self._record(
                name=name,
                category=cat,
                request=f"POST {path}",
                status=status,
                expected=[422],
                body=body,
                expect_rejection=True,
            )

        # Search query / param validation.
        search_cases: list[tuple[str, dict]] = [
            ("search_q_missing", {}),
            ("search_q_empty", {"q": ""}),
            ("search_q_whitespace", {"q": "   "}),
            ("search_limit_zero", {"q": "docker", "limit": 0}),
            ("search_limit_over_max", {"q": "docker", "limit": 99}),
            ("search_limit_non_numeric", {"q": "docker", "limit": "lots"}),
            ("search_format_invalid", {"q": "docker", "format": "verbose"}),
        ]
        for name, params in search_cases:
            status, body, _ = await self._send(
                client, "GET", "/v1/search", params=params, headers=auth
            )
            self._record(
                name=name,
                category=cat,
                request="GET /v1/search",
                status=status,
                expected=[422],
                body=body,
                expect_rejection=True,
            )

    async def _probe_valid_baseline(
        self, client: httpx.AsyncClient, auth: dict[str, str]
    ) -> None:
        cat = "valid_baseline"
        status, body, _ = await self._send(
            client,
            "POST",
            "/v1/problems",
            json={
                "description": "A genuine, well-formed problem description that "
                "comfortably clears the minimum length requirement.",
                "error_signature": "ProbeError: baseline create",
                "tags": ["probe", "baseline"],
            },
            headers=auth,
        )
        self._record(
            name="create_problem_valid",
            category=cat,
            request="POST /v1/problems",
            status=status,
            expected=[201],
            body=body,
            expect_rejection=False,
        )
        status, body, _ = await self._send(
            client, "GET", "/v1/search", params={"q": "docker module"}, headers=auth
        )
        self._record(
            name="search_valid",
            category=cat,
            request="GET /v1/search",
            status=status,
            expected=[200],
            body=body,
            expect_rejection=False,
        )
        status, body, _ = await self._send(
            client,
            "POST",
            f"/v1/solutions/{DEMO_SOLUTION_ID}/outcomes",
            json={"success": True, "notes": "probe baseline outcome"},
            headers=auth,
        )
        self._record(
            name="report_outcome_valid",
            category=cat,
            request="POST /v1/solutions/{id}/outcomes",
            status=status,
            expected=[201],
            body=body,
            expect_rejection=False,
        )

    async def _probe_resource_resolution(
        self, client: httpx.AsyncClient, auth: dict[str, str]
    ) -> None:
        cat = "resource_resolution"
        ghost = str(uuid4())
        valid_body = {
            "content": "A valid solution body that clears the minimum length.",
        }
        cases: list[tuple[str, str, str, list[int], dict | None]] = [
            ("get_problem_bad_uuid", "GET", "/v1/problems/not-a-uuid", [422], None),
            ("get_problem_ghost_uuid", "GET", f"/v1/problems/{ghost}", [404], None),
            (
                "get_timeline_ghost_uuid",
                "GET",
                f"/v1/problems/{ghost}/timeline",
                [404],
                None,
            ),
            (
                "get_lineage_bad_uuid",
                "GET",
                "/v1/solutions/not-a-uuid/lineage",
                [422],
                None,
            ),
            (
                "get_lineage_ghost_uuid",
                "GET",
                f"/v1/solutions/{ghost}/lineage",
                [200, 404],
                None,
            ),
            (
                "create_solution_ghost_problem",
                "POST",
                f"/v1/problems/{ghost}/solutions",
                [404],
                valid_body,
            ),
            (
                "report_outcome_ghost_solution",
                "POST",
                f"/v1/solutions/{ghost}/outcomes",
                [404],
                {"success": True},
            ),
            (
                "improve_ghost_solution",
                "POST",
                f"/v1/solutions/{ghost}/improve",
                [404],
                {
                    "improved_content": "A valid improvement body over the minimum.",
                },
            ),
        ]
        for name, method, path, expected, payload in cases:
            status, body, _ = await self._send(
                client, method, path, json=payload, headers=auth
            )
            self._record(
                name=name,
                category=cat,
                request=f"{method} {path.replace(ghost, '{ghost}')}",
                status=status,
                expected=expected,
                body=body,
                expect_rejection=False,
            )

    async def _probe_auth(self, client: httpx.AsyncClient) -> None:
        cat = "auth"
        good_body = {
            "description": "A valid problem body that clears the minimum length.",
        }
        header_cases: list[tuple[str, dict[str, str]]] = [
            ("write_no_auth", {}),
            ("write_garbage_token", {"Authorization": "Bearer garbage-not-a-key"}),
            ("write_wrong_prefix", {"Authorization": "Bearer sk_wrongprefix12345"}),
            ("write_non_bearer_scheme", {"Authorization": "Token abcdef"}),
            # Scheme only, no token. (A literal "Bearer " with a trailing
            # space is an illegal header value the HTTP client refuses to
            # transmit, so it can never reach the server to be tested.)
            ("write_scheme_only", {"Authorization": "Bearer"}),
        ]
        for name, headers in header_cases:
            status, body, _ = await self._send(
                client, "POST", "/v1/problems", json=good_body, headers=headers
            )
            self._record(
                name=name,
                category=cat,
                request="POST /v1/problems",
                status=status,
                expected=[401],
                body=body,
                expect_rejection=False,
            )
        # verify endpoint with bad credentials.
        status, body, _ = await self._send(
            client, "POST", "/v1/auth/verify", json={"api_key": "ak_not_a_real_key"}
        )
        self._record(
            name="verify_garbage_key",
            category=cat,
            request="POST /v1/auth/verify",
            status=status,
            expected=[401],
            body=body,
            expect_rejection=False,
        )
        status, body, _ = await self._send(
            client, "POST", "/v1/auth/verify", json={"api_key": ""}
        )
        self._record(
            name="verify_empty_key",
            category=cat,
            request="POST /v1/auth/verify",
            status=status,
            expected=[422],
            body=body,
            expect_rejection=True,
        )

    async def _probe_injection(
        self, client: httpx.AsyncClient, auth: dict[str, str]
    ) -> None:
        cat = "injection_content"
        # Search must treat hostile strings as plain text — no crash, no 5xx.
        injection_queries = [
            ("search_sql_injection", "'; DROP TABLE problems; --"),
            ("search_template_injection", "{{7*7}} ${jndi:ldap://x}"),
            ("search_huge_query", "module not found " * 600),
        ]
        for name, query in injection_queries:
            status, body, _ = await self._send(
                client, "GET", "/v1/search", params={"q": query}, headers=auth
            )
            self._record(
                name=name,
                category=cat,
                request="GET /v1/search",
                status=status,
                expected=[200],
                body=body,
                expect_rejection=False,
            )
        # Hostile content in a problem body — accepted or spam-gated, never 5xx.
        content_cases = [
            (
                "create_problem_script_tag",
                "<script>alert(document.cookie)</script> "
                "this describes a real rendering bug in the markdown preview pane.",
            ),
            (
                "create_problem_null_bytes",
                "Problem text with embedded null \x00 "
                "bytes that should be sanitised rather than crash the writer.",
            ),
            (
                "create_problem_unicode",
                "Unicode probe ‮\U0001f4a3 emoji and "
                "right-to-left override in a description of a real layout bug.",
            ),
        ]
        for name, desc in content_cases:
            status, body, _ = await self._send(
                client,
                "POST",
                "/v1/problems",
                json={"description": desc, "tags": ["probe"]},
                headers=auth,
            )
            self._record(
                name=name,
                category=cat,
                request="POST /v1/problems",
                status=status,
                expected=[201, 400],
                body=body,
                expect_rejection=False,
            )
        # Path traversal in a path parameter.
        status, body, _ = await self._send(
            client, "GET", "/v1/problems/..%2F..%2F..%2Fetc%2Fpasswd", headers=auth
        )
        self._record(
            name="path_traversal_problem_id",
            category=cat,
            request="GET /v1/problems/{traversal}",
            status=status,
            expected=[404, 422],
            body=body,
            expect_rejection=False,
        )

    async def _probe_http_semantics(self, client: httpx.AsyncClient) -> None:
        cat = "http_semantics"
        cases: list[tuple[str, str, str, list[int]]] = [
            (
                "get_on_post_route",
                "GET",
                f"/v1/problems/{DEMO_PROBLEM_ID}/solutions",
                [405],
            ),
            ("post_on_get_route", "POST", "/v1/search", [405]),
            ("delete_unsupported", "DELETE", f"/v1/problems/{DEMO_PROBLEM_ID}", [405]),
            ("unknown_route", "GET", "/v1/this-route-does-not-exist", [404]),
        ]
        for name, method, path, expected in cases:
            status, body, _ = await self._send(client, method, path)
            self._record(
                name=name,
                category=cat,
                request=f"{method} {path}",
                status=status,
                expected=expected,
                body=body,
                expect_rejection=False,
            )
        # Malformed JSON body.
        status, body, _ = await self._send(
            client,
            "POST",
            "/v1/auth/register",
            content='{"model_type": "broken',
            headers={"Content-Type": "application/json"},
        )
        self._record(
            name="malformed_json_body",
            category=cat,
            request="POST /v1/auth/register",
            status=status,
            expected=[422],
            body=body,
            expect_rejection=True,
        )

    async def _probe_parameter_validation(
        self, client: httpx.AsyncClient, auth: dict[str, str]
    ) -> None:
        cat = "parameter_validation"
        # /v1/problems list params: sort_by/order are free strings and
        # limit/offset are unconstrained — probe for graceful handling.
        cases: list[tuple[str, dict, list[int]]] = [
            ("list_sort_by_garbage", {"sort_by": "not_a_column"}, [200, 422]),
            ("list_order_garbage", {"order": "sideways"}, [200, 422]),
            ("list_limit_negative", {"limit": -5}, [200, 422]),
            ("list_limit_zero", {"limit": 0}, [200, 422]),
            ("list_offset_negative", {"offset": -10}, [200, 422]),
            ("list_limit_huge", {"limit": 10_000_000}, [200, 422]),
        ]
        for name, params, expected in cases:
            status, body, _ = await self._send(
                client, "GET", "/v1/problems", params=params, headers=auth
            )
            self._record(
                name=name,
                category=cat,
                request="GET /v1/problems",
                status=status,
                expected=expected,
                body=body,
                expect_rejection=False,
            )

    async def _probe_search_rate_limit(self) -> None:
        """A single authenticated agent floods /v1/search past 300/minute."""
        cat = "rate_limit_behavior"
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0),
            headers={"X-Forwarded-For": _IP_SEARCH_FLOOD},
        ) as client:
            reg_status, reg_body, _ = await self._send(
                client, "POST", "/v1/auth/register", json={"model_type": "probe"}
            )
            key = reg_body.get("api_key") if isinstance(reg_body, dict) else None
            if reg_status != 201 or not key:
                self._record(
                    name="search_rate_limit_setup",
                    category=cat,
                    request="POST /v1/auth/register",
                    status=reg_status,
                    expected=[201],
                    body=reg_body,
                    expect_rejection=False,
                )
                return
            auth = {"Authorization": f"Bearer {key}"}
            codes: Counter = Counter()
            saw_envelope = False
            saw_retry_after = False
            for _ in range(330):
                status, body, headers = await self._send(
                    client, "GET", "/v1/search", params={"q": "docker"}, headers=auth
                )
                codes[status] += 1
                if status == 429:
                    if isinstance(body, dict) and isinstance(body.get("error"), dict):
                        saw_envelope = body["error"].get("code") == "rate_limited"
                    if "retry-after" in {k.lower() for k in headers}:
                        saw_retry_after = True
            ok = codes.get(200, 0)
            limited = codes.get(429, 0)
            server_err = sum(c for s, c in codes.items() if s >= 500)
            if server_err:
                verdict, detail = "bug", f"{server_err} server errors during flood"
            elif limited == 0:
                verdict, detail = (
                    "anomaly",
                    f"limiter never triggered after 330 requests ({ok} ok)",
                )
            elif not saw_envelope or not saw_retry_after:
                verdict, detail = (
                    "anomaly",
                    f"429 missing envelope/Retry-After "
                    f"(envelope={saw_envelope}, retry_after={saw_retry_after})",
                )
            else:
                verdict, detail = (
                    "pass",
                    f"{ok} ok then {limited} throttled (300/min enforced)",
                )
            self.results.append(
                ProbeResult(
                    name="search_rate_limit_enforced",
                    category=cat,
                    request="GET /v1/search x330",
                    status_code=429 if limited else 200,
                    expected=[429],
                    verdict=verdict,
                    detail=detail,
                )
            )

    async def _probe_register_rate_limit(self) -> None:
        """A single IP floods /v1/auth/register past 10/hour."""
        cat = "rate_limit_behavior"
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0),
            headers={"X-Forwarded-For": _IP_REGISTER_FLOOD},
        ) as client:
            codes: Counter = Counter()
            for _ in range(13):
                status, _, _ = await self._send(
                    client, "POST", "/v1/auth/register", json={"model_type": "probe"}
                )
                codes[status] += 1
            created = codes.get(201, 0)
            limited = codes.get(429, 0)
            server_err = sum(c for s, c in codes.items() if s >= 500)
            if server_err:
                verdict, detail = "bug", f"{server_err} server errors during flood"
            elif limited == 0:
                verdict, detail = (
                    "anomaly",
                    f"register limiter never triggered ({created} created)",
                )
            elif created > 10:
                verdict, detail = (
                    "anomaly",
                    f"{created} registrations allowed, limit is 10/hour",
                )
            else:
                verdict, detail = (
                    "pass",
                    f"{created} created then {limited} throttled (10/hour enforced)",
                )
            self.results.append(
                ProbeResult(
                    name="register_rate_limit_enforced",
                    category=cat,
                    request="POST /v1/auth/register x13",
                    status_code=429 if limited else 201,
                    expected=[429],
                    verdict=verdict,
                    detail=detail,
                )
            )

    def _record_setup_failure(self, name: str, request: str, detail: str) -> None:
        """Record a probe that could not be set up — an anomaly, not a bug."""
        self.results.append(
            ProbeResult(
                name=name,
                category="rate_limit_behavior",
                request=request,
                status_code=0,
                expected=[201],
                verdict="anomaly",
                detail=detail,
            )
        )

    async def _probe_outcome_rate_limit(self) -> None:
        """A single agent reports on more solutions than the 10/hour cap.

        The cap counts distinct (solution, reporter) outcome rows — repeat
        reports on one solution upsert in place rather than accumulating —
        so the flood must target more than _OUTCOME_RATE_LIMIT distinct
        solutions for the limiter to engage.
        """
        cat = "rate_limit_behavior"
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0),
            headers={"X-Forwarded-For": _IP_OUTCOME_FLOOD},
        ) as client:
            reg_status, reg_body, _ = await self._send(
                client, "POST", "/v1/auth/register", json={"model_type": "probe"}
            )
            key = reg_body.get("api_key") if isinstance(reg_body, dict) else None
            if reg_status != 201 or not key:
                self._record_setup_failure(
                    "outcome_rate_limit_setup",
                    "POST /v1/auth/register",
                    f"probe agent registration failed ({reg_status})",
                )
                return
            auth = {"Authorization": f"Bearer {key}"}

            # Build distinct solutions to report on — one per fresh problem
            # so duplicate-detection never collapses two of them together.
            target = _OUTCOME_RATE_LIMIT + 3
            solution_ids: list[str] = []
            for idx in range(target * 2):
                if len(solution_ids) >= target:
                    break
                p_status, p_body, _ = await self._send(
                    client,
                    "POST",
                    "/v1/problems",
                    json=generate_problem(None, idx),
                    headers=auth,
                )
                if p_status != 201 or not isinstance(p_body, dict):
                    continue
                problem_id = p_body.get("problem_id")
                if not problem_id:
                    continue
                s_status, s_body, _ = await self._send(
                    client,
                    "POST",
                    f"/v1/problems/{problem_id}/solutions",
                    json=generate_solution(),
                    headers=auth,
                )
                if (
                    s_status == 201
                    and isinstance(s_body, dict)
                    and s_body.get("solution_id")
                ):
                    solution_ids.append(s_body["solution_id"])

            if len(solution_ids) <= _OUTCOME_RATE_LIMIT:
                self._record_setup_failure(
                    "outcome_rate_limit_setup",
                    "POST /v1/problems/{id}/solutions",
                    f"only {len(solution_ids)} solutions built, "
                    f"need >{_OUTCOME_RATE_LIMIT} to exercise the cap",
                )
                return

            codes: Counter = Counter()
            for sid in solution_ids:
                status, _, _ = await self._send(
                    client,
                    "POST",
                    f"/v1/solutions/{sid}/outcomes",
                    json={"success": True, "notes": "outcome flood"},
                    headers=auth,
                )
                codes[status] += 1
            created = codes.get(201, 0)
            limited = codes.get(429, 0)
            server_err = sum(c for s, c in codes.items() if s >= 500)
            if server_err:
                verdict, detail = "bug", f"{server_err} server errors during flood"
            elif limited == 0:
                verdict, detail = (
                    "anomaly",
                    f"outcome limiter never triggered ({created} reported)",
                )
            elif created > _OUTCOME_RATE_LIMIT:
                verdict, detail = (
                    "anomaly",
                    f"{created} outcomes allowed, limit is {_OUTCOME_RATE_LIMIT}/hour",
                )
            else:
                verdict, detail = (
                    "pass",
                    f"{created} reported then {limited} throttled "
                    f"({_OUTCOME_RATE_LIMIT}/hour enforced)",
                )
            self.results.append(
                ProbeResult(
                    name="outcome_rate_limit_enforced",
                    category=cat,
                    request=f"POST /v1/solutions/{{id}}/outcomes x{len(solution_ids)}",
                    status_code=429 if limited else 201,
                    expected=[429],
                    verdict=verdict,
                    detail=detail,
                )
            )

    async def _register_fleet(self, count: int) -> list[str]:
        """Register ``count`` agents, each from its own synthetic /32."""
        keys: list[str] = []
        for i in range(count):
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(30.0),
                headers={"X-Forwarded-For": f"{_IP_FLEET_PREFIX}.{i + 1}"},
            ) as client:
                status, body, _ = await self._send(
                    client, "POST", "/v1/auth/register", json={"model_type": "probe"}
                )
                if status == 201 and isinstance(body, dict) and body.get("api_key"):
                    keys.append(body["api_key"])
        return keys

    def _record_concurrent(
        self,
        *,
        name: str,
        request: str,
        runs: list[tuple[int, object, httpx.Headers]],
        accept: set[int],
    ) -> None:
        """Classify a batch of concurrently-issued requests."""
        codes: Counter = Counter(status for status, _, _ in runs)
        server_err = sum(c for s, c in codes.items() if s >= 500)
        transport_fail = codes.get(0, 0)
        unexpected = sorted(
            {s for s in codes if s not in accept and s < 500 and s != 0}
        )
        if server_err or transport_fail:
            verdict = "bug"
            detail = (
                f"{server_err} server errors, {transport_fail} transport "
                f"failures under concurrency; codes={dict(codes)}"
            )
        elif unexpected:
            verdict = "anomaly"
            detail = f"unexpected codes under concurrency; codes={dict(codes)}"
        else:
            verdict = "pass"
            detail = f"codes={dict(codes)}"
        self.results.append(
            ProbeResult(
                name=name,
                category="concurrency",
                request=request,
                status_code=max(codes) if codes else 0,
                expected=sorted(accept),
                verdict=verdict,
                detail=detail,
            )
        )

    async def _probe_concurrency(self) -> None:
        """Hammer shared rows from many agents at once to surface races.

        FastAPI runs the sync routes in a worker threadpool, so these
        requests genuinely execute in parallel against the in-memory
        repositories — a read-modify-write race shows up as a 5xx, a
        transport failure, or an unreadable row afterwards.
        """
        cat = "concurrency"
        keys = await self._register_fleet(12)
        if len(keys) < 6:
            self.results.append(
                ProbeResult(
                    name="concurrency_setup",
                    category=cat,
                    request="POST /v1/auth/register x12",
                    status_code=0,
                    expected=[201],
                    verdict="anomaly",
                    detail=f"only {len(keys)}/12 probe agents registered",
                )
            )
            return
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0),
            headers={"X-Forwarded-For": _IP_CONCURRENCY},
        ) as client:
            # Create a fresh, improvable solution to contend over. A demo
            # solution can be in a terminal state (e.g. demoted) that the
            # service legitimately refuses to improve, which would mask the
            # race the probe is meant to expose.
            owner = {"Authorization": f"Bearer {keys[0]}"}
            p_status, p_body, _ = await self._send(
                client,
                "POST",
                "/v1/problems",
                json=generate_problem(None, 900),
                headers=owner,
            )
            problem_id = p_body.get("problem_id") if isinstance(p_body, dict) else None
            solution_id = None
            if p_status == 201 and problem_id:
                s_status, s_body, _ = await self._send(
                    client,
                    "POST",
                    f"/v1/problems/{problem_id}/solutions",
                    json=generate_solution(),
                    headers=owner,
                )
                if s_status == 201 and isinstance(s_body, dict):
                    solution_id = s_body.get("solution_id")
            if not problem_id or not solution_id:
                self.results.append(
                    ProbeResult(
                        name="concurrency_setup",
                        category=cat,
                        request="POST /v1/problems(+/solutions)",
                        status_code=p_status,
                        expected=[201],
                        verdict="anomaly",
                        detail="could not create a contended fixture",
                    )
                )
                return

            async def _outcome(key: str, ok: bool):
                return await self._send(
                    client,
                    "POST",
                    f"/v1/solutions/{solution_id}/outcomes",
                    json={"success": ok, "notes": "concurrency probe"},
                    headers={"Authorization": f"Bearer {key}"},
                )

            outcome_runs = await asyncio.gather(
                *[_outcome(k, i % 2 == 0) for i, k in enumerate(keys)]
            )
            self._record_concurrent(
                name="concurrent_outcome_reports",
                request=f"POST /v1/solutions/{{id}}/outcomes x{len(keys)} parallel",
                runs=list(outcome_runs),
                accept={201},
            )

            async def _improve(key: str, idx: int):
                # Substantive content so the proposal clears the quality gate
                # and actually reaches the racy evaluate/promote path.
                return await self._send(
                    client,
                    "POST",
                    f"/v1/solutions/{solution_id}/improve",
                    json=generate_improvement(f"probe-{idx}"),
                    headers={"Authorization": f"Bearer {key}"},
                )

            improve_runs = await asyncio.gather(
                *[_improve(k, i) for i, k in enumerate(keys[:8])]
            )
            self._record_concurrent(
                name="concurrent_improvements",
                request="POST /v1/solutions/{id}/improve x8 parallel",
                runs=list(improve_runs),
                accept={200, 409},
            )

            dup_desc = (
                "A duplicate-detection race probe describing one specific "
                "recurring bug submitted by many agents at the same instant."
            )

            async def _create(key: str):
                return await self._send(
                    client,
                    "POST",
                    "/v1/problems",
                    json={"description": dup_desc, "tags": ["probe", "dedup"]},
                    headers={"Authorization": f"Bearer {key}"},
                )

            create_runs = await asyncio.gather(*[_create(k) for k in keys[:10]])
            self._record_concurrent(
                name="concurrent_identical_creates",
                request="POST /v1/problems x10 parallel (identical body)",
                runs=list(create_runs),
                accept={201, 400},
            )

            # The contended problem row must still resolve after the race.
            status, body, _ = await self._send(
                client, "GET", f"/v1/problems/{problem_id}"
            )
            self._record(
                name="post_race_readback",
                category=cat,
                request="GET /v1/problems/{id}",
                status=status,
                expected=[200],
                body=body,
                expect_rejection=False,
            )

    # ── Orchestration ─────────────────────────────────────────────────

    async def run(self) -> list[ProbeResult]:
        """Execute every probe group and return the collected results."""
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0),
            headers={"X-Forwarded-For": _IP_MAIN},
        ) as client:
            reg_status, reg_body, _ = await self._send(
                client, "POST", "/v1/auth/register", json={"model_type": "probe"}
            )
            key = reg_body.get("api_key") if isinstance(reg_body, dict) else None
            if reg_status != 201 or not key:
                raise RuntimeError(
                    f"probe agent registration failed: {reg_status} {reg_body}"
                )
            auth = {"Authorization": f"Bearer {key}"}

            await self._probe_input_validation(client, auth)
            await self._probe_valid_baseline(client, auth)
            await self._probe_resource_resolution(client, auth)
            await self._probe_auth(client)
            await self._probe_injection(client, auth)
            await self._probe_http_semantics(client)
            await self._probe_parameter_validation(client, auth)

        await self._probe_concurrency()
        await self._probe_search_rate_limit()
        await self._probe_register_rate_limit()
        await self._probe_outcome_rate_limit()
        return self.results


def summarize(results: list[ProbeResult]) -> dict:
    """Aggregate probe results into a report section."""
    by_verdict: Counter = Counter(r.verdict for r in results)
    by_category: dict[str, dict[str, int]] = {}
    for r in results:
        cat = by_category.setdefault(r.category, {"pass": 0, "anomaly": 0, "bug": 0})
        cat[r.verdict] += 1
    findings = [
        {
            "name": r.name,
            "category": r.category,
            "request": r.request,
            "status_code": r.status_code,
            "expected": r.expected,
            "verdict": r.verdict,
            "detail": r.detail,
        }
        for r in results
        if r.verdict != "pass"
    ]
    return {
        "total_probes": len(results),
        "passed": by_verdict.get("pass", 0),
        "anomalies": by_verdict.get("anomaly", 0),
        "bugs": by_verdict.get("bug", 0),
        "by_category": by_category,
        "findings": findings,
        "all_probes": [
            {
                "name": r.name,
                "category": r.category,
                "request": r.request,
                "status_code": r.status_code,
                "verdict": r.verdict,
                "detail": r.detail,
            }
            for r in results
        ],
    }


def to_text(summary: dict) -> str:
    """Render a human-readable probe summary."""
    lines = [
        "-" * 70,
        "  Adversarial Deep-Probe Analysis",
        "-" * 70,
        f"  Probes: {summary['total_probes']}  |  "
        f"Passed: {summary['passed']}  |  "
        f"Anomalies: {summary['anomalies']}  |  "
        f"Bugs: {summary['bugs']}",
        "",
    ]
    lines.append("  By category:")
    for cat, counts in summary["by_category"].items():
        lines.append(
            f"    {cat:<24} pass={counts['pass']:>2} "
            f"anomaly={counts['anomaly']:>2} bug={counts['bug']:>2}"
        )
    lines.append("")
    if summary["findings"]:
        lines.append(f"  Findings ({len(summary['findings'])}):")
        for f in summary["findings"]:
            marker = "BUG" if f["verdict"] == "bug" else "ANOMALY"
            lines.append(
                f"    [{marker}] {f['name']} ({f['request']}) -> {f['status_code']}"
            )
            lines.append(f"            {f['detail']}")
    else:
        lines.append("  No bugs or anomalies detected.")
    lines.append("-" * 70)
    return "\n".join(lines)


async def _main() -> int:
    parser = argparse.ArgumentParser(description="AgentBook adversarial probe suite")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    results = await AdversarialProbe(args.base_url).run()
    summary = summarize(results)
    print(to_text(summary))
    print(json.dumps(summary, indent=2, default=str))
    return 1 if summary["bugs"] else 0


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(_main()))
