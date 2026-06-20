"""Standalone sandbox microservice: WSGI dispatch contract.

Pins the HTTP surface RemoteSandboxProvider calls: POST /run with a bearer
token, returns the run verdict JSON; wrong path -> 404; wrong/missing token ->
401; bad body -> 400. The actual docker run is stubbed (the service only owns
dispatch; isolation is the container).
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

_SVC = Path(__file__).resolve().parents[3] / "sandbox_service" / "server.py"


def _load():
    spec = importlib.util.spec_from_file_location("_sandbox_svc", _SVC)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_sandbox_svc"] = module
    spec.loader.exec_module(module)
    return module


_MODULE = _load()


def _call(method="POST", path="/run", body=b"", auth=None, token=""):
    module = _MODULE
    module._TOKEN = token
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
    }
    if auth is not None:
        env["HTTP_AUTHORIZATION"] = auth
    captured = {}

    def sr(status, headers):
        captured["status"] = status

    out = b"".join(module.app(env, sr))
    return captured.get("status"), (json.loads(out) if out else {})


def test_wrong_path_returns_404():
    status, body = _call(method="GET", path="/")
    assert status.startswith("404")


def test_healthz_returns_200_unauthenticated():
    # Railway needs a 2xx healthcheck; /run is POST-only (404 on GET), so
    # /healthz is the liveness path. Must be reachable without a token.
    status, body = _call(method="GET", path="/healthz", token="secret")
    assert status.startswith("200")
    assert body["status"] == "ok"


def test_missing_token_when_configured_returns_401():
    status, body = _call(token="secret", auth=None, body=b"{}")
    assert status.startswith("401")
    assert body["error"] == "unauthorized"


def test_wrong_token_returns_401():
    status, body = _call(token="secret", auth="Bearer wrong", body=b"{}")
    assert status.startswith("401")


def test_valid_request_returns_verdict_json():
    fake_result = {
        "success": True,
        "exit_code": 0,
        "stdout": "hi",
        "stderr": "",
        "duration_seconds": 0.1,
    }
    payload = json.dumps({"code": "print('hi')", "timeout": 5}).encode()
    with patch("_sandbox_svc._run", return_value=fake_result):
        status, body = _call(token="t", auth="Bearer t", body=payload)
    assert status.startswith("200")
    assert body == fake_result


def test_missing_code_returns_400():
    status, body = _call(
        token="t", auth="Bearer t", body=json.dumps({"code": ""}).encode()
    )
    assert status.startswith("400")
    assert body["error"] == "invalid_input"
