"""Subprocess-based sandbox provider for dev/CI environments without Docker."""

from __future__ import annotations

from backend.domain.models import SandboxResult
from backend.infrastructure.sandbox import run_sandboxed


class SubprocessSandboxProvider:
    """Run solution code in a subprocess with timeout.

    Lighter-weight than Docker -- suitable for local dev and CI where
    Docker is unavailable. No network/memory isolation.
    """

    def __init__(self, timeout_seconds: int = 30) -> None:
        self._timeout_seconds = timeout_seconds

    def execute(
        self,
        code: str,
        error_signature: str | None = None,
        timeout_seconds: int | None = None,
        environment: dict | None = None,
    ) -> SandboxResult:
        timeout = timeout_seconds or self._timeout_seconds

        return run_sandboxed(
            lambda _tmpdir, script: ["python3", str(script)],
            code,
            error_signature=error_signature,
            timeout=timeout,
            environment=environment,
        )
