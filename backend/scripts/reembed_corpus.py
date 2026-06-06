"""Backfill ``problems.embedding_v2`` with the configured embedding provider.

Iterates approved problems in batches, embeds them with
``input_type="document"`` at ``EMBEDDING_DIMENSION`` dimensions, and writes
them to ``problems.embedding_v2`` via the side-channel ``update_embedding_v2``
method. The provider is whatever ``resolve_search_stack`` selects (Gemini →
Voyage → OpenRouter → Fallback), so a model/provider change is picked up by
re-running with ``--force``.

Idempotent + resumable: ``WHERE embedding_v2 IS NULL`` is the natural
checkpoint — re-running picks up where a crashed run left off. Use
``--force`` to re-embed every problem (e.g., after a model change).

Usage::

    DATABASE_URL=postgresql://... \\
    GEMINI_API_KEY=... EMBEDDING_VERSION=v2 \\
    uv run python -m backend.scripts.reembed_corpus [--dry-run] [--batch 128] [--force]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

logger = logging.getLogger("agentbook.reembed")


def _build_provider():
    """Resolve the configured embedding provider, exiting fast if none is real.

    Uses the same resolver as the live API (``resolve_search_stack``) so the
    backfill embeds with whatever provider production runs. Refuses the
    deterministic Fallback — backfilling with it would poison ``embedding_v2``
    with non-semantic vectors.
    """
    from backend.infrastructure.embeddings.fallback import FallbackEmbeddingProvider
    from backend.infrastructure.search_stack import resolve_search_stack

    stack = resolve_search_stack()
    if isinstance(stack.embedding_provider, FallbackEmbeddingProvider):
        print(
            "error: no real embedding provider configured "
            "(set GEMINI_API_KEY / VOYAGE_API_KEY / OPENROUTER_API_KEY)",
            file=sys.stderr,
        )
        sys.exit(2)
    return stack.embedding_provider


def _embed_documents(provider, texts: list[str]) -> list[list[float]]:
    """Use the provider's native batch path when present, else embed one by one."""
    batch = getattr(provider, "embed_documents", None)
    if callable(batch):
        return batch(texts)
    return [provider.embed(text, input_type="document") for text in texts]


def _candidates_query(force: bool):
    from sqlalchemy import select

    from backend.infrastructure.persistence.sqlalchemy_models import ProblemORM

    stmt = select(ProblemORM.problem_id, ProblemORM.description).where(
        ProblemORM.review_status == "approved",
    )
    if not force:
        stmt = stmt.where(ProblemORM.embedding_v2.is_(None))
    return stmt.order_by(ProblemORM.created_at.asc())


def reembed(batch_size: int, dry_run: bool, force: bool) -> int:
    """Run the backfill. Returns the number of problems re-embedded."""
    from backend.infrastructure.persistence.database import SessionLocal
    from backend.infrastructure.persistence.sqlalchemy_repositories import (
        SQLAlchemyProblemRepository,
    )

    repo = SQLAlchemyProblemRepository(SessionLocal)
    provider = _build_provider() if not dry_run else None

    with SessionLocal() as session:
        rows = session.execute(_candidates_query(force)).all()
    total = len(rows)
    logger.info(
        "backfill-start total=%d batch_size=%d dry_run=%s", total, batch_size, dry_run
    )

    processed = 0
    for offset in range(0, total, batch_size):
        chunk = rows[offset : offset + batch_size]
        ids = [str(r[0]) for r in chunk]
        texts = [r[1] for r in chunk]
        if dry_run:
            logger.info(
                "dry-run-batch offset=%d size=%d head_id=%s",
                offset,
                len(chunk),
                ids[0] if ids else "-",
            )
            processed += len(chunk)
            continue

        start = time.monotonic()
        vectors = _embed_documents(provider, texts)
        embed_dt_ms = int((time.monotonic() - start) * 1000)

        for problem_id, vector in zip(ids, vectors, strict=True):
            from uuid import UUID

            repo.update_embedding_v2(UUID(problem_id), vector)
        processed += len(chunk)
        logger.info(
            "batch-done offset=%d size=%d embed_ms=%d processed=%d/%d",
            offset,
            len(chunk),
            embed_dt_ms,
            processed,
            total,
        )

    logger.info("backfill-complete processed=%d", processed)
    return processed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch", type=int, default=128, help="rows fetched/written per loop iteration"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="enumerate without embedding"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-embed every approved problem (default: only NULL embedding_v2)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    reembed(batch_size=args.batch, dry_run=args.dry_run, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
