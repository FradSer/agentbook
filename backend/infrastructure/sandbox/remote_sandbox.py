"""Remote sandbox provider — POST code to a dedicated sandbox microservice.

For hosts with no Docker daemon (e.g. a Railway app container, where setting
``SANDBOX_ENABLED=true`` crashes boot because ``docker info`` fails), the API
service never runs untrusted code in-process. Instead it POSTs the code to a
separate sandbox microservice (which IS a Docker host, or wraps a cloud
code-execution API) over HTTP. That service owns isolation; the API only owns
the contract.

The sandbox service contract is a single endpoint:
    POST {sandbox_service_url}/run
        body: {"code": str, "error_signature": str|null, "timeout": int,
               "environment": dict|null}
        header: Authorization: Bearer {sandbox_service_token}
    -> 200 {"success": bool, "exit_code": int, "stdout": str, "stderr": str,
            "duration_seconds": float, "environment": dict}
    -> non-200: treated as an execution error (success=False).

This mirrors the local ``run_sandboxed`` result shape so the service layer is
unaware of which provider served the run.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from backend.domain.models import SandboxResult

_DEFAULT_TIMEOUT = 60.0


class RemoteSandboxProvider:
    """Run solution code via a remote sandbox microservice.

    The provider is transport-only: it serializes the run request and
    deserializes the verdict. All isolation (network egress, memory/CPU caps,
    image choice) is the sandbox service's responsibility, not the API's.
    """

    def __init__(
        self,
        service_url: str,
        token: str | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self._url = service_url.rstrip("/") + "/run"
        self._token = token
        self._timeout_seconds = timeout_seconds

    def execute(
        self,
        code: str,
        error_signature: str | None = None,
        timeout_seconds: int | None = None,
        environment: dict | None = None,
    ) -> SandboxResult:
        timeout = timeout_seconds or self._timeout_seconds
        payload = json.dumps(
            {
                "code": code,
                "error_signature": error_signature,
                "timeout": timeout,
                "environment": environment or {},
            }
        ).encode()
        req = urllib.request.Request(self._url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        if self._token:
            req.add_header("Authorization", f"Bearer {self._token}")
        try:
            with urllib.request.urlopen(req, timeout=_DEFAULT_TIMEOUT) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"sandbox service HTTP {exc.code}: {exc.reason}",
                duration_seconds=0.0,
                environment=environment or {},
            )
        except (urllib.error.URLError, TimeoutError) as exc:
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"sandbox service unreachable: {exc}",
                duration_seconds=0.0,
                environment=environment or {},
            )
        return SandboxResult(
            success=bool(body.get("success", False)),
            exit_code=int(body.get("exit_code", -1)),
            stdout=str(body.get("stdout", ""))[:4096],
            stderr=str(body.get("stderr", ""))[:4096],
            duration_seconds=round(float(body.get("duration_seconds", 0.0)), 3),
            environment=environment or {},
        )
