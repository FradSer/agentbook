"""Verifies the contract described in features/proxy_headers.feature.

Production runs behind Railway's edge proxy. The Railway start command
must pass ``--proxy-headers --forwarded-allow-ips=*`` to uvicorn so that
slowapi's ``get_remote_address`` resolves the client tier of the
X-Forwarded-For chain instead of the proxy IP. Without this, every
anonymous caller collapses into a single global rate-limit bucket.

The first two tests pin the runtime behaviour of uvicorn's
``ProxyHeadersMiddleware`` so a future dependency bump that silently
changes the parsing strategy fails CI. The third test pins the
railway.toml flags themselves.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from slowapi.util import get_remote_address
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


def _whoami(request: Request) -> JSONResponse:
    return JSONResponse({"remote": get_remote_address(request)})


def _make_app() -> Starlette:
    return Starlette(routes=[Route("/whoami", _whoami)])


class TestProxyHeadersMiddleware:
    def test_with_proxy_headers_middleware_returns_forwarded_client_ip(self) -> None:
        app = ProxyHeadersMiddleware(_make_app(), trusted_hosts="*")
        client = TestClient(app)
        resp = client.get(
            "/whoami",
            headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1"},
        )
        assert resp.status_code == 200
        assert resp.json()["remote"] == "203.0.113.7"

    def test_without_proxy_headers_middleware_returns_direct_client_ip(self) -> None:
        client = TestClient(_make_app())
        resp = client.get(
            "/whoami",
            headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1"},
        )
        assert resp.status_code == 200
        # starlette's TestClient reports the in-process loopback
        # ("testclient"), proving the X-Forwarded-For chain is ignored
        # when ProxyHeadersMiddleware is absent.
        assert resp.json()["remote"] != "203.0.113.7"


class TestRailwayStartCommandFlags:
    """Pin railway.toml so the proxy-headers flags can't be silently dropped."""

    def test_start_command_carries_proxy_headers_flags(self) -> None:
        railway_toml = Path(__file__).resolve().parents[4] / "railway.toml"
        config = tomllib.loads(railway_toml.read_text())
        start = config["deploy"]["startCommand"]

        # Only assert when the API branch is present (agent branch is also in
        # this command via a runtime env switch — both branches share one line).
        assert "uvicorn backend.main:app" in start, (
            "Backend uvicorn invocation missing from start command"
        )
        assert "--proxy-headers" in start, (
            "Production start command must include --proxy-headers; without it "
            "slowapi.get_remote_address resolves to the proxy IP and every "
            "anonymous caller collapses into one global rate-limit bucket."
        )
        assert re.search(r"--forwarded-allow-ips[= ]\*", start), (
            "Production start command must trust forwarded headers from any "
            "origin (Railway's edge IP rotates)."
        )
