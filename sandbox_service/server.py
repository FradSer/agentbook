"""Standalone sandbox microservice.

A tiny HTTP service that runs submitted Python code in an isolated Docker
container (Docker-in-Docker). Deployed as its OWN Railway service (which is a
Docker host), distinct from the API service (which has no Docker daemon).

Contract (mirrors what RemoteSandboxProvider calls):

    POST /run
        Authorization: Bearer $SANDBOX_SERVICE_TOKEN
        body: {"code": str, "error_signature": str|null,
               "timeout": int, "environment": dict|null}
    -> 200 {"success": bool, "exit_code": int, "stdout": str, "stderr": str,
            "duration_seconds": float, "environment": dict}

Security: bearer-token gated, runs code with --network=none, memory+cpu caps,
--rm cleanup, and a hard outer timeout. The image is pinned python:3.11-slim.

Run locally:
    SANDBOX_SERVICE_TOKEN=secret python sandbox_service/server.py
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

_IMAGE = "python:3.11-slim"
_MEMORY_MB = "128"
_DEFAULT_TIMEOUT = 30
_TOKEN = os.environ.get("SANDBOX_SERVICE_TOKEN", "")
_MAX_CODE_BYTES = 200_000


def _run(code: str, error_signature: str | None, timeout: int) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        script = Path(tmpdir) / "solution.py"
        script.write_text(code)
        cmd = [
            "docker",
            "run",
            "--rm",
            "--network=none",
            f"--memory={_MEMORY_MB}m",
            "--cpus=0.5",
            "-v",
            f"{tmpdir}:/work:ro",
            _IMAGE,
            "python",
            "/work/solution.py",
        ]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = time.monotonic() - start
            success = proc.returncode == 0
            if error_signature and error_signature in proc.stderr:
                success = False
            return {
                "success": success,
                "exit_code": proc.returncode,
                "stdout": proc.stdout[:4096],
                "stderr": proc.stderr[:4096],
                "duration_seconds": round(duration, 3),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Timeout after {timeout}s",
                "duration_seconds": round(time.monotonic() - start, 3),
            }


def app(environ, start_response):
    """WSGI app — no framework dependency, stdlib only."""
    method = environ.get("REQUEST_METHOD", "")
    path = environ.get("PATH_INFO", "")
    if method != "POST" or path != "/run":
        start_response("404 Not Found", [("Content-Type", "application/json")])
        return [json.dumps({"error": "not_found"}).encode()]

    auth = environ.get("HTTP_AUTHORIZATION", "")
    if _TOKEN and auth != f"Bearer {_TOKEN}":
        start_response("401 Unauthorized", [("Content-Type", "application/json")])
        return [json.dumps({"error": "unauthorized"}).encode()]

    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
        body = environ["wsgi.input"].read(length) if length else b""
        payload = json.loads(body.decode() or "{}")
    except (ValueError, json.JSONDecodeError):
        start_response("400 Bad Request", [("Content-Type", "application/json")])
        return [json.dumps({"error": "invalid_input"}).encode()]

    code = str(payload.get("code", ""))
    if not code or len(code) > _MAX_CODE_BYTES:
        start_response("400 Bad Request", [("Content-Type", "application/json")])
        return [
            json.dumps({"error": "invalid_input", "detail": "code required"}).encode()
        ]

    result = _run(
        code,
        payload.get("error_signature"),
        int(payload.get("timeout") or _DEFAULT_TIMEOUT),
    )
    start_response("200 OK", [("Content-Type", "application/json")])
    return [json.dumps(result).encode()]


if __name__ == "__main__":
    from wsgiref.simple_server import make_server

    port = int(os.environ.get("PORT", "8080"))
    print(f"sandbox-service on :{port} (image={_IMAGE})", flush=True)
    make_server("0.0.0.0", port, app).serve_forever()
