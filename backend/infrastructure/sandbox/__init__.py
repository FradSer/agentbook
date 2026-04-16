"""Sandbox execution providers.

Factory function resolves the active provider based on configuration.
Shared helper for the write-file/run/capture pipeline used by both providers.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from backend.core.config import settings
from backend.domain.models import SandboxResult
from backend.domain.services import SandboxProvider

logger = logging.getLogger(__name__)


def run_sandboxed(
    build_cmd: Callable[[str, Path], list[str]],
    code: str,
    *,
    error_signature: str | None = None,
    timeout: int = 30,
    environment: dict | None = None,
) -> SandboxResult:
    """Write code to a temp file, execute a command, and return a SandboxResult.

    *build_cmd* receives ``(tmpdir, script_path)`` and returns the
    command list.  Both Docker and subprocess providers delegate here
    so timing, error-signature check, output truncation, and exception
    handling live in one place.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        script = Path(tmpdir) / "solution.py"
        script.write_text(code)
        cmd = build_cmd(tmpdir, script)

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
            )
            duration = time.monotonic() - start

            success = proc.returncode == 0
            if error_signature and error_signature in proc.stderr:
                success = False

            return SandboxResult(
                success=success,
                exit_code=proc.returncode,
                stdout=proc.stdout[:4096],
                stderr=proc.stderr[:4096],
                duration_seconds=round(duration, 3),
                environment=environment or {},
            )
        except subprocess.TimeoutExpired:
            duration = time.monotonic() - start
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Timeout after {timeout}s",
                duration_seconds=round(duration, 3),
                environment=environment or {},
            )
        except Exception:
            duration = time.monotonic() - start
            logger.warning("Sandbox execution failed", exc_info=True)
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Sandbox execution error",
                duration_seconds=round(duration, 3),
                environment=environment or {},
            )


def resolve_sandbox_provider() -> SandboxProvider:
    """Return a sandbox provider based on the current environment.

    - Docker provider when a Docker daemon is reachable.
    - Subprocess fallback for dev/CI.
    """
    from backend.infrastructure.sandbox.docker_sandbox import DockerSandboxProvider

    try:
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
