from __future__ import annotations

import os
import socket
import subprocess
import time
import uuid

import pytest


pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(os.getenv("RUN_DOCKER_TESTS") != "1", reason="Set RUN_DOCKER_TESTS=1"),
]


def _run(command: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_alembic_migration_creates_pgvector_and_ltree_extensions() -> None:
    container_name = f"agentbook-test-{uuid.uuid4().hex[:8]}"
    db_user = "agentbook"
    db_pass = "agentbook"
    db_name = "agentbook"
    port = _pick_free_port()
    database_url = f"postgresql://{db_user}:{db_pass}@127.0.0.1:{port}/{db_name}"

    try:
        _run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                container_name,
                "-e",
                f"POSTGRES_USER={db_user}",
                "-e",
                f"POSTGRES_PASSWORD={db_pass}",
                "-e",
                f"POSTGRES_DB={db_name}",
                "-p",
                f"{port}:5432",
                "pgvector/pgvector:pg16",
            ]
        )

        ready = False
        for _ in range(30):
            status = subprocess.run(
                [
                    "docker",
                    "exec",
                    container_name,
                    "pg_isready",
                    "-U",
                    db_user,
                    "-d",
                    db_name,
                ],
                text=True,
                capture_output=True,
            )
            if status.returncode == 0:
                ready = True
                break
            time.sleep(1)

        assert ready, "PostgreSQL container did not become ready in time"

        env = os.environ.copy()
        env["DATABASE_URL"] = database_url
        _run(["uv", "run", "alembic", "upgrade", "head"], env=env)

        extensions = _run(
            [
                "docker",
                "exec",
                container_name,
                "psql",
                "-U",
                db_user,
                "-d",
                db_name,
                "-t",
                "-c",
                "SELECT extname FROM pg_extension WHERE extname IN ('vector', 'ltree') ORDER BY extname;",
            ]
        )

        normalized = {line.strip() for line in extensions.stdout.splitlines() if line.strip()}
        assert normalized == {"ltree", "vector"}

        schema_check = _run(
            [
                "docker",
                "exec",
                container_name,
                "psql",
                "-U",
                db_user,
                "-d",
                db_name,
                "-t",
                "-c",
                "SELECT to_regclass('public.threads'), to_regclass('public.comments'), to_regclass('public.votes');",
            ]
        )
        assert "threads" in schema_check.stdout
        assert "comments" in schema_check.stdout
        assert "votes" in schema_check.stdout
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], check=False, capture_output=True)
