"""Campaign-book synthesis providers.

``BookSynthesizer`` (Protocol in ``backend.domain.services``) is the
contract. ``LLMBookSynthesizer`` is the default in-process implementation
using the Cloudflare AI Gateway. ``resolve_book_synthesizer`` returns None
when Gateway credentials are not configured so the service falls back to a
mechanical render.
"""

from backend.infrastructure.synthesis.book_synthesizer import (
    LLMBookSynthesizer,
    resolve_book_synthesizer,
)

__all__ = ["LLMBookSynthesizer", "resolve_book_synthesizer"]
