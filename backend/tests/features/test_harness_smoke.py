"""Smoke test proving the shared cross-transport harness imports and wires.

This is intentionally minimal: it asserts the four shared fixtures
(``rest_client``, ``mcp_client``, ``assert_transport_parity``,
``embedding_fault``) resolve and that both transport callers run end-to-end
against one in-memory ``AgentbookService``. Feature tasks build their real
scenarios on top of these fixtures.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def test_transport_callers_run_against_shared_service(
    rest_client: Callable[..., dict[str, Any]],
    mcp_client: Callable[..., dict[str, Any]],
) -> None:
    rest_payload = rest_client("nothing here yet")
    mcp_payload = mcp_client("nothing here yet")
    assert "results" in rest_payload
    assert "results" in mcp_payload


def test_embedding_fault_factory_produces_each_mode(
    embedding_fault: Callable[[str], Any],
) -> None:
    slow = embedding_fault("slow", delay_seconds=0.0)
    assert slow.embed("x") == [0.0] * 1024

    failing = embedding_fault("failing")
    try:
        failing.embed("x")
    except RuntimeError:
        pass
    else:  # pragma: no cover - guards against a silent regression
        raise AssertionError("failing mode must raise")

    mismatch = embedding_fault("dimension_mismatch")
    assert len(mismatch.embed("x")) == 1536


def test_assert_transport_parity_fixture_is_callable(
    assert_transport_parity: Callable[..., dict[str, Any]],
) -> None:
    assert callable(assert_transport_parity)
