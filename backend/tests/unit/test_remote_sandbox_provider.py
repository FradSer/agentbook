"""RemoteSandboxProvider POSTs code to a sandbox microservice and parses the verdict.

Covers the contract a dedicated sandbox service must honor: POST /run with
code/error_signature/timeout/environment, Bearer token, returns success +
exit_code + stdout + stderr + duration. Unreachable / errored service degrades
to a failed SandboxResult (never raises into the caller).
"""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from backend.domain.models import SandboxResult
from backend.infrastructure.sandbox.remote_sandbox import RemoteSandboxProvider


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self) -> bytes:
        return self._body


def _provider(**kw) -> RemoteSandboxProvider:
    return RemoteSandboxProvider(
        service_url=kw.get("url", "https://sandbox.example.com"),
        token=kw.get("token", "tok"),
        timeout_seconds=kw.get("timeout", 30),
    )


def test_success_run_posts_code_and_parses_verdict() -> None:
    provider = _provider()
    captured: dict = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.method
        captured["auth"] = req.headers.get("Authorization")
        captured["body"] = json.loads(req.data.decode())
        return _FakeResponse(
            json.dumps(
                {
                    "success": True,
                    "exit_code": 0,
                    "stdout": "ok\n",
                    "stderr": "",
                    "duration_seconds": 0.42,
                }
            ).encode()
        )

    with patch(
        "backend.infrastructure.sandbox.remote_sandbox.urllib.request.urlopen",
        side_effect=fake_urlopen,
    ):
        result = provider.execute(
            "print('hi')", error_signature="Boom", timeout_seconds=15
        )

    assert captured["url"].endswith("/run")
    assert captured["method"] == "POST"
    assert captured["auth"] == "Bearer tok"
    assert captured["body"]["code"] == "print('hi')"
    assert captured["body"]["error_signature"] == "Boom"
    assert captured["body"]["timeout"] == 15
    assert isinstance(result, SandboxResult)
    assert result.success is True
    assert result.exit_code == 0
    assert result.stdout == "ok\n"
    assert result.duration_seconds == 0.42


def test_no_token_omits_authorization_header() -> None:
    provider = _provider(token=None)
    seen: dict = {}

    def fake_urlopen(req, timeout=None):
        seen["auth"] = req.headers.get("Authorization")
        return _FakeResponse(json.dumps({"success": False, "exit_code": 1}).encode())

    with patch(
        "backend.infrastructure.sandbox.remote_sandbox.urllib.request.urlopen",
        side_effect=fake_urlopen,
    ):
        provider.execute("x")

    assert seen["auth"] is None


def test_http_error_degrades_to_failed_result_not_raise() -> None:
    provider = _provider()

    def fake_urlopen(req, timeout=None):
        raise HTTPError(req.full_url, 503, "Unavailable", {}, BytesIO(b""))

    with patch(
        "backend.infrastructure.sandbox.remote_sandbox.urllib.request.urlopen",
        side_effect=fake_urlopen,
    ):
        result = provider.execute("x")

    assert result.success is False
    assert "503" in result.stderr


def test_unreachable_service_degrades_to_failed_result_not_raise() -> None:
    provider = _provider()

    def fake_urlopen(req, timeout=None):
        raise URLError("connection refused")

    with patch(
        "backend.infrastructure.sandbox.remote_sandbox.urllib.request.urlopen",
        side_effect=fake_urlopen,
    ):
        result = provider.execute("x")

    assert result.success is False
    assert "unreachable" in result.stderr
