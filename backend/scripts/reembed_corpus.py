"""Backfill ``problems.embedding_v2`` with Voyage v3-large embeddings.

Phase 3b of the false-positive fix migration. Iterates approved problems in
batches of 128 (Voyage accepts up to 1000 inputs per call; 128 is the
conservative pick that keeps memory tame on Railway), embeds them with
``input_type="document"`` at 1024 dimensions, and writes them to
``problems.embedding_v2`` via the side-channel
``update_embedding_v2`` method.

Idempotent + resumable: ``WHERE embedding_v2 IS NULL`` is the natural
checkpoint — re-running picks up where a crashed run left off. Use
``--force`` to re-embed every problem (e.g., after a model change).

Usage::

    DATABASE_URL=postgresql://... \\
    VOYAGE_API_KEY=ak_voyage_... \\
    uv run python -m backend.scripts.reembed_corpus [--dry-run] [--batch 128] [--force]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

logger = logging.getLogger("agentbook.reembed")


def _build_voyage_provider():
    """Construct a Voyage embedder from env, exiting fast on misconfiguration."""
    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        print("error: VOYAGE_API_KEY must be set", file=sys.stderr)
        sys.exit(2)

    from backend.infrastructure.embeddings.voyage import VoyageEmbeddingProvider

    return VoyageEmbeddingProvider(
        api_key=api_key,
        model=os.environ.get("VOYAGE_EMBEDDING_MODEL", "voyage-3-large"),
        output_dimension=int(os.environ.get("EMBEDDING_DIMENSION", "1024")),
    )


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
    provider = _build_voyage_provider() if not dry_run else None

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
        vectors = provider.embed_documents(texts)  # type: ignore[union-attr]
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
        "--batch", type=int, default=128, help="batch size for Voyage embed calls"
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
