"""Docker-based sandbox provider for production use.

Runs solution code in an isolated container with no network access and
constrained memory/CPU. This is the primary sandbox backend.
"""

from __future__ import annotations

from backend.domain.models import SandboxResult
from backend.infrastructure.sandbox import run_sandboxed


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
        image = self._image
        memory_mb = self._memory_mb

        def build_cmd(tmpdir: str, _script):
            return [
                "docker",
                "run",
                "--rm",
                "--network=none",
                f"--memory={memory_mb}m",
                "--cpus=0.5",
                "-v",
                f"{tmpdir}:/work:ro",
                image,
                "python",
                "/work/solution.py",
            ]

        return run_sandboxed(
            build_cmd,
            code,
            error_signature=error_signature,
            timeout=timeout,
            environment=environment,
        )
