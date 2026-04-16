"""No-op sandbox provider for unit tests.

Always returns a successful result without executing anything.
"""

from __future__ import annotations

from backend.domain.models import SandboxResult


class NoopSandboxProvider:
    """Sandbox stub that always reports success. Used in unit tests."""

    def execute(
        self,
        code: str,
        error_signature: str | None = None,
        timeout_seconds: int = 30,
        environment: dict | None = None,
    ) -> SandboxResult:
        return SandboxResult(
            success=True,
            exit_code=0,
            stdout="",
            stderr="",
            duration_seconds=0.0,
            environment=environment or {},
        )
