"""Docker-based sandbox provider for production use.

Runs solution code in an isolated container with no network access and
constrained memory/CPU. This is the primary sandbox backend.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import time
from pathlib import Path

from backend.domain.models import SandboxResult

logger = logging.getLogger(__name__)


class DockerSandboxProvider:
    """Run solution code inside a Docker container.

    Security constraints:
    - ``--network=none`` blocks all outbound traffic.
    - ``--memory`` caps RAM usage.
    - ``--cpus=0.5`` limits CPU.
    - ``--rm`` cleans up the container after exit.
    """

    def __init__(
        self,
        image: str = "python:3.11-slim",
        timeout_seconds: int = 30,
        memory_mb: int = 128,
    ) -> None:
        self._image = image
        self._timeout_seconds = timeout_seconds
        self._memory_mb = memory_mb

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

            cmd = [
                "docker",
                "run",
                "--rm",
                "--network=none",
                f"--memory={self._memory_mb}m",
                "--cpus=0.5",
                "-v",
                f"{tmpdir}:/work:ro",
                self._image,
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
                # Kill any lingering container
                return SandboxResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Docker timeout after {timeout}s",
                    duration_seconds=round(duration, 3),
                    environment=environment or {},
                )
            except Exception:
                duration = time.monotonic() - start
                logger.warning("Docker sandbox execution failed", exc_info=True)
                return SandboxResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr="Docker sandbox error",
                    duration_seconds=round(duration, 3),
                    environment=environment or {},
                )
