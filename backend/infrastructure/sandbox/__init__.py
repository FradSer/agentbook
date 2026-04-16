"""Sandbox execution providers.

Factory function resolves the active provider based on configuration.
"""

from __future__ import annotations

from backend.core.config import settings
from backend.domain.services import SandboxProvider


def resolve_sandbox_provider() -> SandboxProvider:
    """Return a sandbox provider based on the current environment.

    - Docker provider when a Docker daemon is reachable.
    - Subprocess fallback for dev/CI.
    """
    from backend.infrastructure.sandbox.docker_sandbox import DockerSandboxProvider

    try:
        import subprocess

        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
            check=True,
        )
        return DockerSandboxProvider(
            image=settings.sandbox_image,
            timeout_seconds=settings.sandbox_timeout_seconds,
            memory_mb=settings.sandbox_memory_mb,
        )
    except Exception:
        from backend.infrastructure.sandbox.subprocess_sandbox import (
            SubprocessSandboxProvider,
        )

        return SubprocessSandboxProvider(
            timeout_seconds=settings.sandbox_timeout_seconds,
        )
