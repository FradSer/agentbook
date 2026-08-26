"""Verifies features/embedding-failover.feature.

Runtime failover across configured embedding providers: one expired API key
(prod incident 2026-08-26, Gemini API_KEY_INVALID while the Voyage key was
valid) must not degrade every search to keyword mode. Failed providers enter
a cooldown; recovery is retried after it; single-provider stacks keep their
exact identity and name.
"""

from __future__ import annotations

import time

import pytest

from backend.infrastructure.embeddings.failover import FailoverEmbeddingProvider


class FakeProvider:
    def __init__(self, name: str, error: Exception | None = None):
        self.name = name
        self.error = error
        self.calls = 0

    def embed(self, text: str, *, input_type: str = "query") -> list[float]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return [0.1, 0.2]


def test_first_provider_failure_fails_over_in_request() -> None:
    gemini = FakeProvider("gemini", error=RuntimeError("API_KEY_INVALID"))
    voyage = FakeProvider("voyage")
    chain = FailoverEmbeddingProvider(
        [("gemini", gemini), ("voyage", voyage)], cooldown_seconds=60.0
    )
    vector = chain.embed("probe")
    assert vector == [0.1, 0.2]
    assert gemini.calls == 1
    assert voyage.calls == 1
    assert chain.active_index == 1


def test_failed_provider_not_retried_inside_cooldown() -> None:
    gemini = FakeProvider("gemini", error=RuntimeError("API_KEY_INVALID"))
    voyage = FakeProvider("voyage")
    chain = FailoverEmbeddingProvider(
        [("gemini", gemini), ("voyage", voyage)], cooldown_seconds=60.0
    )
    chain.embed("first")
    chain.embed("second")
    assert gemini.calls == 1, "cooldown must suppress immediate retry"
    assert voyage.calls == 2


def test_recovered_provider_becomes_active_after_cooldown() -> None:
    gemini = FakeProvider("gemini", error=RuntimeError("quota"))
    voyage = FakeProvider("voyage")
    chain = FailoverEmbeddingProvider(
        [("gemini", gemini), ("voyage", voyage)], cooldown_seconds=0.05
    )
    chain.embed("during cooldown")
    time.sleep(0.06)
    gemini.error = None
    chain.embed("after cooldown")
    assert gemini.calls == 2
    assert chain.active_index == 0


def test_all_providers_failing_raises_runtime_error() -> None:
    a = FakeProvider("a", error=RuntimeError("down a"))
    b = FakeProvider("b", error=RuntimeError("down b"))
    chain = FailoverEmbeddingProvider([("a", a), ("b", b)], cooldown_seconds=60.0)
    with pytest.raises(RuntimeError, match="all embedding providers failed"):
        chain.embed("probe")


def test_name_chain_reflects_priority_order() -> None:
    chain = FailoverEmbeddingProvider(
        [
            ("gemini", FakeProvider("gemini")),
            ("voyage", FakeProvider("voyage")),
            ("openrouter", FakeProvider("openrouter")),
        ]
    )
    assert chain.name_chain == "gemini>voyage>openrouter"
