"""Integration test configuration.

Integration tests require a live PostgreSQL instance and are only collected
when RUN_DOCKER_TESTS=1 is set in the environment. This prevents import-time
failures from blocking the default unit-test run.
"""

from __future__ import annotations

import os

collect_ignore_glob: list[str] = []

if not os.getenv("RUN_DOCKER_TESTS"):
    # Skip all integration tests when no real DB is available.
    # pytest discovers this list before importing test modules, so stale
    # imports in those modules do not cause collection errors.
    collect_ignore_glob = ["test_*.py"]
