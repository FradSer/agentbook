"""Campaign-book synthesis providers.

``BookSynthesizer`` (Protocol in ``backend.domain.services``) is the
contract. ``LLMBookSynthesizer`` is the default in-process implementation
(httpx -> OpenRouter, mirroring ``llm_evaluator.py``). ``resolve_book_synthesizer``
returns None when no OpenRouter key is configured so the service falls back
to a mechanical render.
"""

from backend.infrastructure.synthesis.book_synthesizer import (
    LLMBookSynthesizer,
    resolve_book_synthesizer,
)

__all__ = ["LLMBookSynthesizer", "resolve_book_synthesizer"]
