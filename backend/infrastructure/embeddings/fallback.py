from __future__ import annotations

from backend.core.config import settings


class FallbackEmbeddingProvider:
    """Deterministic local embedding for environments without an API key."""

    def embed(self, text: str, *, input_type: str = "query") -> list[float]:
        # Symmetric provider; ``input_type`` is accepted for Protocol parity
        # with asymmetric encoders such as Voyage v3-large but has no effect.
        del input_type
        lowered = text.lower()
        dimension = settings.embedding_dimension
        vector = [0.0] * dimension
        if dimension == 0:
            return vector

        vector[0] = 1.0 if "error" in lowered else 0.0
        if dimension > 1:
            vector[1] = 1.0 if "python" in lowered else 0.0
        if dimension > 2:
            vector[2] = 1.0 if "mcp" in lowered or "fastmcp" in lowered else 0.0
        if dimension > 3:
            vector[3] = min(len(lowered), 500) / 500.0

        for index, char in enumerate(lowered[: min(len(lowered), dimension)]):
            bucket = index % dimension
            vector[bucket] += (ord(char) % 17) / 100.0
        return vector
