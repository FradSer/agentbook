"""Runtime failover across configured embedding providers.

The search stack resolves providers by key PRESENCE at startup, but keys can
die at runtime (prod incident 2026-08-26: Gemini API_KEY_INVALID while the
Voyage key stayed valid — every search degraded to keyword mode because the
static choice was never revisited). This wrapper tries the chain in priority
order per request, puts a failing provider on a short cooldown so dead keys
are not retried on every call, and recovers automatically once the cooldown
elapses.
"""

from __future__ import annotations

import logging
import time

from backend.domain.services import EmbeddingProvider

logger = logging.getLogger(__name__)

_DEFAULT_COOLDOWN_SECONDS = 60.0


class FailoverEmbeddingProvider:
    """Priority-ordered embedding chain with sticky health and cooldown."""

    def __init__(
        self,
        providers: list[tuple[str, EmbeddingProvider]],
        *,
        cooldown_seconds: float = _DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        if not providers:
            raise ValueError("FailoverEmbeddingProvider needs at least one provider")
        self._entries = list(providers)
        self._cooldown_seconds = cooldown_seconds
        self._cooldown_until = [0.0] * len(self._entries)
        self.active_index = 0

    @property
    def name_chain(self) -> str:
        return ">".join(name for name, _ in self._entries)

    def embed(self, text: str, *, input_type: str = "query") -> list[float]:
        now = time.monotonic()
        last_error: Exception | None = None
        # Always attempt in priority order (skipping cooled-down entries): a
        # higher-priority provider that recovered must be promoted back
        # automatically, so "active" records who served last but does not
        # freeze the order.
        for index in range(len(self._entries)):
            if now < self._cooldown_until[index]:
                continue
            name, provider = self._entries[index]
            try:
                result = provider.embed(text, input_type=input_type)
                if index != self.active_index:
                    logger.warning("embedding provider %s became active", name)
                    self.active_index = index
                return result
            except Exception as e:  # noqa: BLE001
                self._cooldown_until[index] = time.monotonic() + self._cooldown_seconds
                if len(self._entries) > 1:
                    logger.warning(
                        "embedding provider %s failed; trying next in chain: %s",
                        name,
                        e,
                    )
                last_error = e
        raise RuntimeError(
            f"all embedding providers failed ({self.name_chain}): {last_error}"
        )
