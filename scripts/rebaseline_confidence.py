#!/usr/bin/env python
"""Re-baseline confidence on a pre-pilot agentbook deployment.

Every confidence score in a pre-pilot commons is driven by seeded outcomes
(``organic_external == 0``). A public read that shows a seeded solution at
0.96+ confidence with zero organic reporters contradicts the product's
"confidence is earned from real outcomes" contract. This script returns the
corpus to the honest cold-start baseline: it removes the seeded outcome rows
and resets every solution/problem confidence to ``BASELINE_CONFIDENCE``.

It is DRY-RUN by default and refuses to mutate unless the live usage
dashboard confirms 100% of outcomes are non-organic (seeded), so it can only
ever delete seed data, never a real external report.

    # inspect only (default)
    uv run --package agentbook python scripts/rebaseline_confidence.py

    # mutate, after reading the dry-run
    uv run --package agentbook python scripts/rebaseline_confidence.py \
        --apply --yes-i-am-sure
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import urllib.request
from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from backend.application.confidence import BASELINE_CONFIDENCE
from backend.core.config import settings
from backend.infrastructure.persistence.database import SessionLocal, engine
from backend.infrastructure.persistence.sqlalchemy_models import (
    OutcomeORM,
    ProblemORM,
    SolutionORM,
)

DEFAULT_API = "https://agentbook-api-production.up.railway.app"


def _fetch_usage(api_base: str) -> dict:
    url = f"{api_base.rstrip('/')}/v1/dashboard/usage"
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 (trusted host)
        return json.load(resp)


def _redacted_db_host() -> str:
    parts = urlsplit(settings.database_url or "")
    return f"{parts.scheme}://…@{parts.hostname}:{parts.port or ''}{parts.path}"


def _assert_all_seeded(usage: dict) -> int:
    """Confirm every outcome is non-organic; return the seeded total."""
    src = usage.get("outcome_sources", {})
    organic = src.get("organic_external", {}).get("total", 0)
    author_self = src.get("author_self", {}).get("total", 0)
    synthetic = src.get("synthetic", {}).get("total", 0)
    seeded = src.get("seeded", {}).get("total", 0)
    total = usage.get("outcomes", {}).get("total", 0)
    print("  live dashboard outcome_sources:")
    print(
        f"    seeded={seeded}  synthetic={synthetic}  "
        f"author_self={author_self}  organic_external={organic}  total={total}"
    )
    if organic or author_self or synthetic:
        sys.exit(
            "ABORT: dashboard reports non-seeded outcomes "
            f"(organic={organic}, author_self={author_self}, synthetic={synthetic}). "
            "This script only re-baselines a 100%-seeded corpus; resolve those "
            "rows manually first."
        )
    return total


def _snapshot(session) -> dict:
    n_out = session.scalar(select(func.count()).select_from(OutcomeORM))
    n_sol_above = session.scalar(
        select(func.count())
        .select_from(SolutionORM)
        .where(SolutionORM.confidence > BASELINE_CONFIDENCE)
    )
    n_prob_above = session.scalar(
        select(func.count())
        .select_from(ProblemORM)
        .where(ProblemORM.best_confidence > BASELINE_CONFIDENCE)
    )
    n_promoted = session.scalar(
        select(func.count())
        .select_from(SolutionORM)
        .where(SolutionORM.promotion_status == "promoted")
    )
    n_canonical = session.scalar(
        select(func.count())
        .select_from(ProblemORM)
        .where(ProblemORM.canonical_solution_id.isnot(None))
    )
    top = session.execute(
        select(
            SolutionORM.solution_id,
            SolutionORM.confidence,
            SolutionORM.outcome_count,
            SolutionORM.promotion_status,
        )
        .order_by(SolutionORM.confidence.desc())
        .limit(6)
    ).all()
    return {
        "outcomes": n_out,
        "solutions_above_baseline": n_sol_above,
        "problems_above_baseline": n_prob_above,
        "promoted_solutions": n_promoted,
        "canonical_pointers": n_canonical,
        "top": top,
    }


def _print_snapshot(label: str, snap: dict) -> None:
    print(f"\n{label}")
    print(f"  outcome rows:                 {snap['outcomes']}")
    print(
        f"  solutions confidence > {BASELINE_CONFIDENCE}:   "
        f"{snap['solutions_above_baseline']}"
    )
    print(
        f"  problems best_confidence > {BASELINE_CONFIDENCE}: "
        f"{snap['problems_above_baseline']}"
    )
    print(f"  'promoted' solutions:         {snap['promoted_solutions']}")
    print(f"  canonical pointers set:       {snap['canonical_pointers']}")
    print("  highest-confidence solutions:")
    for sid, conf, n, status in snap["top"]:
        print(f"    {conf:.3f}  outcomes={n:<3} {status or '-':<10} {sid}")


def _backup_state(session) -> str:
    """Dump everything the re-baseline mutates so it is reversible: the deleted
    outcome rows, plus the solution promotion_status and problem canonical
    pointers that get reset (the numbers alone are not enough to roll back)."""
    outcomes = [
        {c.name: getattr(r, c.name) for c in OutcomeORM.__table__.columns}
        for r in session.execute(select(OutcomeORM)).scalars().all()
    ]
    promotions = [
        {"solution_id": sid, "promotion_status": status}
        for sid, status in session.execute(
            select(SolutionORM.solution_id, SolutionORM.promotion_status)
        ).all()
    ]
    canonicals = [
        {"problem_id": pid, "canonical_solution_id": cid}
        for pid, cid in session.execute(
            select(ProblemORM.problem_id, ProblemORM.canonical_solution_id)
        ).all()
    ]
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    path = f"/tmp/agentbook_rebaseline_backup_{stamp}.json"
    with open(path, "w") as fh:
        json.dump(
            {
                "outcomes": outcomes,
                "solution_promotions": promotions,
                "problem_canonicals": canonicals,
            },
            fh,
            default=str,
            indent=1,
        )
    print(
        f"  backed up {len(outcomes)} outcomes + {len(promotions)} promotions "
        f"+ {len(canonicals)} canonical pointers -> {path}"
    )
    return path
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--api-base",
        default=DEFAULT_API,
        help="API base for the authoritative usage dashboard",
    )
    ap.add_argument("--apply", action="store_true", help="mutate the database")
    ap.add_argument(
        "--yes-i-am-sure",
        action="store_true",
        help="required second confirmation for --apply",
    )
    args = ap.parse_args()

    if engine is None:
        sys.exit("ABORT: DATABASE_URL is not set; nothing to re-baseline.")

    print("Target database:", _redacted_db_host())
    print("Authoritative dashboard:", args.api_base)
    print("\n[1/3] Verifying every outcome is seeded (non-organic)…")
    usage = _fetch_usage(args.api_base)
    dash_total = _assert_all_seeded(usage)

    # Serverless Postgres (and Railway's wake-on-connect proxy) drops the
    # first connections while it spins up; ride through the cold start.
    for attempt in range(6):
        try:
            SessionLocal().execute(select(1)).all()
            break
        except OperationalError as exc:
            if attempt == 5:
                raise
            print(
                f"  db not ready (attempt {attempt + 1}/6): "
                f"{str(exc).splitlines()[0][:80]}… retrying"
            )
            time.sleep(3)

    session = SessionLocal()
    try:
        before = _snapshot(session)
        if before["outcomes"] != dash_total:
            sys.exit(
                f"ABORT: DB outcome count {before['outcomes']} != dashboard "
                f"total {dash_total}; refusing to act on a mismatched view."
            )
        _print_snapshot("[2/3] BEFORE state:", before)

        if not args.apply:
            print(
                "\n[3/3] DRY RUN — no changes written. Re-run with "
                "--apply --yes-i-am-sure to delete the seeded outcomes, reset "
                f"all confidence to {BASELINE_CONFIDENCE}, clear 'promoted' "
                "statuses and stale canonical pointers."
            )
            return

        if not args.yes_i_am_sure:
            sys.exit("ABORT: --apply requires --yes-i-am-sure.")

        print("\n[3/3] APPLYING re-baseline…")
        backup = _backup_state(session)
        deleted = session.query(OutcomeORM).delete(synchronize_session=False)
        reset_sol = session.query(SolutionORM).update(
            {
                SolutionORM.confidence: BASELINE_CONFIDENCE,
                SolutionORM.outcome_count: 0,
                SolutionORM.success_count: 0,
                SolutionORM.failure_count: 0,
            },
            synchronize_session=False,
        )
        # Reset the STATE the wiped outcomes justified, not just the numbers.
        # A 'promoted' status with zero outcomes paints a public "Confirmed"
        # badge that contradicts the honest-baseline contract — clear it.
        # 'demoted' is left as-is so rejected proposals stay hidden rather than
        # resurfacing as visible 0.3 solutions.
        cleared_promoted = (
            session.query(SolutionORM)
            .filter(SolutionORM.promotion_status == "promoted")
            .update({SolutionORM.promotion_status: None}, synchronize_session=False)
        )
        # A synthesized canonical built on now-erased outcomes is stale; null the
        # pointer so the book falls back to the highest-confidence history entry.
        cleared_canonical = (
            session.query(ProblemORM)
            .filter(ProblemORM.canonical_solution_id.isnot(None))
            .update({ProblemORM.canonical_solution_id: None}, synchronize_session=False)
        )
        # Only problems that actually have a solution carry a confidence.
        problems_with_solutions = select(SolutionORM.problem_id).distinct()
        reset_prob = (
            session.query(ProblemORM)
            .filter(ProblemORM.problem_id.in_(problems_with_solutions))
            .update(
                {ProblemORM.best_confidence: BASELINE_CONFIDENCE},
                synchronize_session=False,
            )
        )
        session.commit()
        print(
            f"  deleted {deleted} outcomes; reset {reset_sol} solutions "
            f"({cleared_promoted} promoted->base), cleared {cleared_canonical} "
            f"canonical pointers, reset {reset_prob} problems. Backup: {backup}"
        )
        _print_snapshot("AFTER state:", _snapshot(session))
    finally:
        session.close()


if __name__ == "__main__":
    main()
