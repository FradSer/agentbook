"""Contract tests: the contribute write path advises against forking duplicates.

Feature file: backend/tests/features/write-dedup.feature

When a contributed problem matches a known one (by error_signature or
description), the write response must populate ``existing_problems`` so an agent
can switch to improve-mode. The error_signature leg must work WITHOUT embeddings
(the autouse fixture forces ``openrouter_api_key=None`` -> keyword fallback).
"""

from __future__ import annotations

import json
from uuid import UUID

from backend.tests.conftest import _build_contract_service


def _seed_problem(ctx, description, error_signature=None):
    service = ctx["service"]
    return service.create_problem(
        author_id=ctx["author"].agent_id,
        description=description,
        error_signature=error_signature,
    )


def _build():
    service, ctx = _build_contract_service()
    ctx["service"] = service
    return service, ctx


def test_identical_error_signature_surfaces_existing_problem():
    service, ctx = _build()
    sig = "RuntimeError: Event loop is closed"
    prior = _seed_problem(
        ctx,
        "asyncpg connection raises on interpreter shutdown after the loop closes",
        error_signature=sig,
    )

    result = service.contribute(
        author_id=ctx["author"].agent_id,
        description="Another service hits the closed event loop on teardown path",
        error_signature=sig,
    )

    existing = result.get("existing_problems") or []
    assert existing, "identical error_signature must surface the prior problem"
    ids = [e["problem_id"] for e in existing]
    assert str(prior.problem_id) in ids
    # Advises improve-mode (provide solution_id) over forking.
    advisory = json.dumps(result).lower()
    assert "solution_id" in advisory or "improve" in advisory


def test_near_identical_description_surfaces_existing_problem():
    service, ctx = _build()
    prior = _seed_problem(
        ctx,
        "asyncpg connection pool close raises RuntimeError during application "
        "shutdown when the event loop is already closed",
        error_signature="RuntimeError: Event loop is closed",
    )

    result = service.contribute(
        author_id=ctx["author"].agent_id,
        description="asyncpg connection pool close raises RuntimeError during "
        "shutdown because the event loop is already closed",
        error_signature="RuntimeError: Event loop is closed",
    )

    existing = result.get("existing_problems") or []
    assert existing, "paraphrased duplicate must populate existing_problems"
    assert str(prior.problem_id) in [e["problem_id"] for e in existing]
    assert existing[0]["match_quality"] in ("strong", "exact")


def test_novel_problem_reports_no_existing_match():
    service, ctx = _build()
    _seed_problem(
        ctx,
        "asyncpg connection pool close raises RuntimeError on shutdown",
        error_signature="RuntimeError: Event loop is closed",
    )

    result = service.contribute(
        author_id=ctx["author"].agent_id,
        description="Tailwind JIT purge strips dynamically composed class names "
        "in the production build output",
        error_signature="UnknownAtRule: @apply unknown utility",
    )

    assert not (result.get("existing_problems") or [])
    # A genuinely novel problem is still created.
    assert ctx["problems"].get(UUID(result["problem_id"])) is not None


def test_remember_tool_description_steers_recall_first():
    from backend.presentation.mcp.tools import TOOL_DEFINITIONS

    remember = next(t for t in TOOL_DEFINITIONS if t.name == "remember")
    desc = remember.description.lower()
    assert "recall" in desc
    assert "improve" in desc
