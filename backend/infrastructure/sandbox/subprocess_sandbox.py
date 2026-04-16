"""Subprocess-based sandbox provider for dev/CI environments without Docker."""

from __future__ import annotations

import logging
import subprocess
import tempfile
import time
from pathlib import Path

from backend.domain.models import SandboxResult

logger = logging.getLogger(__name__)


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

        with tempfile.TemporaryDirectory() as tmpdir:
            script = Path(tmpdir) / "solution.py"
            script.write_text(code)

            start = time.monotonic()
            try:
                proc = subprocess.run(
                    ["python3", str(script)],
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
                logger.warning("Subprocess sandbox execution failed", exc_info=True)
                return SandboxResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr="Sandbox execution error",
                    duration_seconds=round(duration, 3),
                    environment=environment or {},
                )
