from __future__ import annotations

from app.core.config import settings
from app.infrastructure.embeddings.fallback import FallbackEmbeddingProvider


def test_fallback_embedding_dimension_matches_config() -> None:
    provider = FallbackEmbeddingProvider()

    vector = provider.embed("ModuleNotFoundError fastmcp")

    assert len(vector) == settings.embedding_dimension
