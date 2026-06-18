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
import urllib.request
from urllib.parse import urlsplit

from sqlalchemy import func, select

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
    print("  highest-confidence solutions:")
    for sid, conf, n, status in snap["top"]:
        print(f"    {conf:.3f}  outcomes={n:<3} {status or '-':<10} {sid}")


def _backup_outcomes(session) -> str:
    rows = session.execute(select(OutcomeORM)).scalars().all()
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    path = f"/tmp/agentbook_outcomes_backup_{stamp}.json"
    dump = [
        {c.name: getattr(r, c.name) for c in OutcomeORM.__table__.columns} for r in rows
    ]
    with open(path, "w") as fh:
        json.dump(dump, fh, default=str, indent=1)
    print(f"  backed up {len(dump)} outcome rows -> {path}")
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
                "--apply --yes-i-am-sure to delete the seeded outcomes and "
                f"reset all confidence to {BASELINE_CONFIDENCE}."
            )
            return

        if not args.yes_i_am_sure:
            sys.exit("ABORT: --apply requires --yes-i-am-sure.")

        print("\n[3/3] APPLYING re-baseline…")
        backup = _backup_outcomes(session)
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
            f"  deleted {deleted} outcomes; reset {reset_sol} solutions, "
            f"{reset_prob} problems. Backup: {backup}"
        )
        _print_snapshot("AFTER state:", _snapshot(session))
    finally:
        session.close()


if __name__ == "__main__":
    main()
