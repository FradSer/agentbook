"""Standalone sandbox microservice — e2b cloud backend (default) or DinD.

The API service has no Docker daemon and runs on a non-privileged Railway
container, so neither DinD-on-the-API nor a privileged sandbox service works on
standard Railway. The deployable path is a **cloud code-execution backend**
(e2b): this service is a thin adapter that takes the RemoteSandboxProvider
contract (POST /run) and delegates execution to e2b's cloud sandbox. Isolation
lives in e2b, not in our process — so this service runs unprivileged and safe.

Backend selection (auto):
  - E2B_API_KEY set  -> e2b cloud (the deployable path on Railway)
  - else              -> local Docker-in-Docker (dev only; needs a privileged host)

Contract (what RemoteSandboxProvider calls):
    POST /run
        Authorization: Bearer $SANDBOX_SERVICE_TOKEN
        body: {"code": str, "error_signature": str|null,
               "timeout": int, "environment": dict|null}
    -> 200 {"success": bool, "exit_code": int, "stdout": str, "stderr": str,
            "duration_seconds": float, "environment": dict}
"""

from __future__ import annotations

import json
import os
import time

_TOKEN = os.environ.get("SANDBOX_SERVICE_TOKEN", "")
_E2B_KEY = os.environ.get("E2B_API_KEY", "")
_MAX_CODE_BYTES = 200_000
_DEFAULT_TIMEOUT = 30


def _run_e2b(code: str, timeout: int) -> dict:
    """Run code via e2b cloud sandbox. Isolation is e2b's responsibility."""
    from e2b_code_interpreter import Sandbox

    start = time.monotonic()
    try:
        with Sandbox(api_key=_E2B_KEY, timeout=timeout) as sbx:
            execution = sbx.run_code(code, timeout=timeout)
        duration = time.monotonic() - start
        stdout = "".join(execution.logs.stdout) if execution.logs else ""
        stderr = "".join(execution.logs.stderr) if execution.logs else ""
        if execution.error:
            stderr = (stderr + "\n" + str(execution.error)).strip()
            return {
                "success": False,
                "exit_code": 1,
                "stdout": stdout[:4096],
                "stderr": stderr[:4096],
                "duration_seconds": round(duration, 3),
            }
        return {
            "success": True,
            "exit_code": 0,
            "stdout": stdout[:4096],
            "stderr": stderr[:4096],
            "duration_seconds": round(duration, 3),
        }
    except Exception as exc:  # e2b SDK/network/timeout errors
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"e2b execution error: {exc}",
            "duration_seconds": round(time.monotonic() - start, 3),
        }


def _run_dind(code: str, error_signature, timeout: int) -> dict:
    """Local Docker-in-Docker fallback (dev only — needs a privileged host)."""
    import subprocess
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        script = Path(tmpdir) / "solution.py"
        script.write_text(code)
        cmd = [
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--memory=128m",
            "--cpus=0.5",
            "-v",
            f"{tmpdir}:/work:ro",
            "python:3.11-slim",
            "python",
            "/work/solution.py",
        ]
        start = time.monotonic()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
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
        except FileNotFoundError:
            # No docker binary on this host (the non-privileged Railway case
            # without an E2B_API_KEY). Return a clear failure instead of a 500
            # so the API surfaces a usable verdict rather than a server crash.
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": (
                    "no execution backend available: set E2B_API_KEY for the "
                    "e2b cloud backend (the DinD fallback needs a Docker daemon "
                    "not present on this host)"
                ),
                "duration_seconds": round(time.monotonic() - start, 3),
            }


def _run_pyodide(code: str, timeout: int) -> dict:
    """Run code in Pyodide (WASM Python) via a Node subprocess.

    The self-hosted, KEY-FREE sandbox backend: the WASM linear-memory boundary
    is the isolation — no host filesystem, no raw sockets, no privileged
    container, no Docker daemon, no third-party API key. Needs only Node +
    the pyodide npm package (cold-start downloads the WASM runtime once).
    """
    import json as _json
    import subprocess
    from pathlib import Path

    runner = Path(__file__).parent / "pyodide_runner.mjs"
    start = time.monotonic()
    try:
        proc = subprocess.Popen(
            ["node", str(runner)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, err = proc.communicate(
            input=_json.dumps({"code": code, "timeout": timeout}),
            timeout=timeout + 15,  # WASM cold start can take time
        )
        duration = time.monotonic() - start
        if out.strip():
            result = _json.loads(out.strip().splitlines()[-1])
            result["duration_seconds"] = round(duration, 3)
            return result
        return {
            "success": False,
            "exit_code": proc.returncode,
            "stdout": "",
            "stderr": (err or "pyodide runner produced no output")[:4096],
            "duration_seconds": round(duration, 3),
        }
    except subprocess.TimeoutExpired:
        proc.kill()
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"pyodide runner timeout after {timeout}s",
            "duration_seconds": round(time.monotonic() - start, 3),
        }
    except FileNotFoundError:
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "node not found; install node to use the pyodide backend",
            "duration_seconds": round(time.monotonic() - start, 3),
        }


def _run(code: str, error_signature, timeout: int) -> dict:
    # Resolution order: e2b (cloud, best) -> pyodide (self-hosted, key-free,
    # WASM isolation) -> DinD (dev only). Pyodide makes the sandbox work with
    # zero operator setup, removing the last external-key dependency.
    if _E2B_KEY:
        return _run_e2b(code, timeout)
    if os.environ.get("SANDBOX_DISABLE_PYODIDE") != "1":
        return _run_pyodide(code, timeout)
    return _run_dind(code, error_signature, timeout)


def app(environ, start_response):
    """WSGI app — stdlib only, no framework."""
    method = environ.get("REQUEST_METHOD", "")
    path = environ.get("PATH_INFO", "")
    # Unauthenticated liveness probe — Railway requires a 2xx healthcheck, and
    # /run's POST-only contract returns 404 on a GET, so expose /healthz.
    if method == "GET" and path == "/healthz":
        start_response("200 OK", [("Content-Type", "application/json")])
        return [json.dumps({"status": "ok"}).encode()]
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
    backend = "e2b" if _E2B_KEY else "dind (dev)"
    print(f"sandbox-service on :{port} (backend={backend})", flush=True)
    make_server("0.0.0.0", port, app).serve_forever()
