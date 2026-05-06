"""Recalibrate the dedup similarity threshold for Voyage v3-large.

The hard-coded ``find_similar(threshold=0.9)`` at
``backend/application/service.py`` was tuned for OpenAI
``text-embedding-3-small`` (1536-dim, symmetric). Voyage v3-large at 1024-dim
has a measurably different cosine distribution — a 0.9 threshold under
Voyage will likely either over-merge or stop catching dupes.

This script samples the current corpus, embeds all sampled descriptions
with Voyage, computes pairwise cosines for known dupe / non-dupe pairs, and
prints the threshold that maximises F1. The operator pastes the chosen
value into ``backend.application.service`` (or sets a future
``DEDUP_THRESHOLD`` env var) before flipping ``EMBEDDING_VERSION=v2``.

Ground truth comes from the existing ``ProblemRelationship`` table where
``relationship_type='vector_similarity'`` represents Reviewer-confirmed
duplicates and disjoint pairs serve as negatives.

Usage::

    DATABASE_URL=postgresql://... \\
    VOYAGE_API_KEY=ak_voyage_... \\
    uv run python -m backend.scripts.calibrate_dedup_threshold [--samples 200]
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import random
import sys

logger = logging.getLogger("agentbook.calibrate")


def _cosine(a: list[float], b: list[float]) -> float:
    """Plain cosine similarity; assumes both vectors are non-empty same dim."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def calibrate(samples: int) -> dict:
    from sqlalchemy import select

    from backend.infrastructure.embeddings.voyage import VoyageEmbeddingProvider
    from backend.infrastructure.persistence.database import SessionLocal
    from backend.infrastructure.persistence.sqlalchemy_models import (
        ProblemORM,
        ProblemRelationshipORM,
    )

    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        print("error: VOYAGE_API_KEY must be set", file=sys.stderr)
        sys.exit(2)

    provider = VoyageEmbeddingProvider(
        api_key=api_key,
        model=os.environ.get("VOYAGE_EMBEDDING_MODEL", "voyage-3-large"),
        output_dimension=int(os.environ.get("EMBEDDING_DIMENSION", "1024")),
    )

    with SessionLocal() as session:
        # Positive pairs: ProblemRelationships marked vector_similarity by
        # the Reviewer (a confirmed-dupe ground truth).
        rels = session.execute(
            select(
                ProblemRelationshipORM.problem_id,
                ProblemRelationshipORM.related_problem_id,
            ).where(ProblemRelationshipORM.relationship_type == "vector_similarity")
        ).all()
        positive_pairs = [(str(a), str(b)) for a, b in rels]

        # Random negatives — sample two random approved problems that have
        # no relationship row.
        all_ids = [
            str(pid)
            for (pid,) in session.execute(
                select(ProblemORM.problem_id).where(
                    ProblemORM.review_status == "approved"
                )
            ).all()
        ]
        positives_set = {tuple(sorted(p)) for p in positive_pairs}
        random.seed(42)
        negatives: list[tuple[str, str]] = []
        guard = 0
        while (
            len(negatives) < min(samples, len(positive_pairs)) and guard < samples * 20
        ):
            a, b = random.sample(all_ids, 2)
            guard += 1
            if tuple(sorted((a, b))) in positives_set:
                continue
            negatives.append((a, b))

        unique_ids = sorted(
            {pid for pair in positive_pairs + negatives for pid in pair}
        )
        descriptions = {
            row.problem_id: row.description
            for row in session.execute(
                select(ProblemORM).where(
                    ProblemORM.problem_id.in_(unique_ids[: samples * 2])
                )
            ).scalars()
        }

    logger.info(
        "samples positives=%d negatives=%d unique_ids=%d",
        len(positive_pairs),
        len(negatives),
        len(unique_ids),
    )

    # Embed every unique description once.
    texts = [descriptions[pid] for pid in unique_ids if pid in descriptions]
    vectors_list = provider.embed_documents(texts)
    vectors = dict(
        zip(
            [pid for pid in unique_ids if pid in descriptions],
            vectors_list,
            strict=True,
        )
    )

    def cosines(pairs):
        scores = []
        for a, b in pairs:
            if a in vectors and b in vectors:
                scores.append(_cosine(vectors[a], vectors[b]))
        return scores

    pos_scores = cosines(positive_pairs[:samples])
    neg_scores = cosines(negatives[:samples])
    if not pos_scores or not neg_scores:
        print(
            "error: not enough labelled pairs to calibrate "
            f"(pos={len(pos_scores)}, neg={len(neg_scores)})",
            file=sys.stderr,
        )
        sys.exit(3)

    # Sweep thresholds and pick the one that maximises F1.
    best = {"threshold": 0.5, "f1": 0.0, "precision": 0.0, "recall": 0.0}
    for cut in (i / 100 for i in range(40, 100)):
        tp = sum(1 for s in pos_scores if s >= cut)
        fn = len(pos_scores) - tp
        fp = sum(1 for s in neg_scores if s >= cut)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            (2 * precision * recall) / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        if f1 > best["f1"]:
            best = {
                "threshold": round(cut, 3),
                "f1": round(f1, 3),
                "precision": round(precision, 3),
                "recall": round(recall, 3),
            }

    return {
        "best": best,
        "positives": len(pos_scores),
        "negatives": len(neg_scores),
        "pos_mean": round(sum(pos_scores) / len(pos_scores), 3) if pos_scores else 0,
        "neg_mean": round(sum(neg_scores) / len(neg_scores), 3) if neg_scores else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=200)
    args = parser.parse_args()
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    result = calibrate(samples=args.samples)
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
