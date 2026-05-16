from __future__ import annotations

import os
import socket
import subprocess
import time
import uuid

import pytest

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        os.getenv("RUN_DOCKER_TESTS") != "1", reason="Set RUN_DOCKER_TESTS=1"
    ),
]


def _run(
    command: list[str], env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
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


def test_alembic_migration_produces_expected_schema() -> None:
    """Full migration chain on a pgvector-enabled Postgres.

    The embedding columns must end up as ``json`` even though the ``vector``
    extension is available: the ORM binds embeddings as JSON lists via
    ``FlexibleVector``, so a real ``vector`` column would reject every
    ``problems`` write with ``DatatypeMismatch``. This guards the P0
    regression fixed by the ``q2r3s4t5u6v7`` migration.
    """
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
                "SELECT extname FROM pg_extension WHERE extname = 'vector';",
            ]
        )

        normalized = {
            line.strip() for line in extensions.stdout.splitlines() if line.strip()
        }
        assert normalized == {"vector"}

        # Forum-era tables (threads/comments/votes/token_transactions) were dropped in
        # f5g6h7i8j9k0_unify_v1_v2 and c6dadb0fd799_remove_token_economy.
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
                "SELECT to_regclass('public.threads'), to_regclass('public.comments'), "
                "to_regclass('public.votes'), to_regclass('public.token_transactions');",
            ]
        )
        for name in ("threads", "comments", "votes", "token_transactions"):
            assert name not in schema_check.stdout, (
                f"{name} table should have been dropped by later migrations"
            )

        # P0 guard: embedding columns must be json, never pgvector ``vector``,
        # even though the extension is installed above.
        column_types = _run(
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
                "SELECT column_name || ':' || data_type "
                "FROM information_schema.columns "
                "WHERE table_name = 'problems' "
                "AND column_name IN ('embedding', 'embedding_v2');",
            ]
        )
        type_map = dict(
            line.strip().split(":")
            for line in column_types.stdout.splitlines()
            if line.strip()
        )
        assert type_map == {"embedding": "json", "embedding_v2": "json"}, (
            f"embedding columns must be json (FlexibleVector binds JSON); "
            f"got {type_map}"
        )

        vector_indexes = _run(
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
                "SELECT count(*) FROM pg_indexes WHERE tablename = 'problems' "
                "AND (indexdef ILIKE '%hnsw%' OR indexdef ILIKE '%ivfflat%');",
            ]
        )
        assert vector_indexes.stdout.strip() == "0", (
            "no ivfflat/HNSW index may exist on the json embedding columns"
        )
    finally:
        subprocess.run(
            ["docker", "rm", "-f", container_name], check=False, capture_output=True
        )
