#!/usr/bin/env python3
"""Private ledger and public-query sanitizer for the Codex dogfood pilot."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pilot_ledger import (
    DEFAULT_EXPERIMENT_SEED,
    DEFAULT_LEDGER,
    VALID_ARMS,
    VALID_COHORTS,
    VALID_RECALL_STATES,
    PilotLedger,
    assign_arm,
    summarize,
)
from pilot_privacy import sanitize_error
from pilot_recall import DEFAULT_BASE_URL, recall_public

__all__ = [
    "PilotLedger",
    "assign_arm",
    "recall_public",
    "sanitize_error",
    "summarize",
]


def _ledger_from_args(args: argparse.Namespace) -> PilotLedger:
    return PilotLedger(Path(args.ledger), experiment_seed=args.seed)


def _read_error(args: argparse.Namespace) -> str:
    return args.error if args.error is not None else sys.stdin.read()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger",
        default=os.environ.get("AGENTBOOK_PILOT_LEDGER", str(DEFAULT_LEDGER)),
    )
    parser.add_argument(
        "--seed",
        default=os.environ.get("AGENTBOOK_PILOT_SEED", DEFAULT_EXPERIMENT_SEED),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    sanitize = commands.add_parser("sanitize")
    sanitize.add_argument("--error", help="raw error; omit to read stdin")
    sanitize.add_argument("--dependency", action="append", default=[])
    sanitize.add_argument("--private-term", action="append", default=[])

    start = commands.add_parser("start")
    start.add_argument("--error", help="raw error; omit to read stdin")
    start.add_argument("--repo", required=True)
    start.add_argument("--dependency", action="append", default=[])
    start.add_argument("--private-term", action="append", default=[])
    start.add_argument("--incident-id")
    start.add_argument("--cohort", choices=sorted(VALID_COHORTS), default="live")
    start.add_argument("--pair-id")
    start.add_argument("--arm", choices=sorted(VALID_ARMS))

    recall = commands.add_parser("recall")
    recall.add_argument("--incident-id", required=True)
    recall.add_argument("--crossover", action="store_true")
    recall.add_argument(
        "--base-url",
        default=os.environ.get("AGENTBOOK_BASE_URL", DEFAULT_BASE_URL),
    )

    finish = commands.add_parser("finish")
    finish.add_argument("--incident-id", required=True)
    finish.add_argument("--first-attempt", choices=["passed", "failed"], required=True)
    finish.add_argument(
        "--pre-recall", choices=sorted(VALID_RECALL_STATES), required=True
    )
    finish.add_argument(
        "--crossover-recall", choices=sorted(VALID_RECALL_STATES), default="not_called"
    )
    finish.add_argument("--verification", required=True)
    finish.add_argument("--match-quality")
    finish.add_argument("--solution-id")

    commands.add_parser("summary")
    return parser


def _run_command(args: argparse.Namespace) -> Any:
    if args.command == "sanitize":
        return asdict(
            sanitize_error(
                _read_error(args),
                args.dependency,
                private_terms=args.private_term,
            )
        )
    if args.command == "start":
        return _ledger_from_args(args).start(
            error=_read_error(args),
            repository=args.repo,
            dependencies=args.dependency,
            private_terms=args.private_term,
            incident_id=args.incident_id,
            cohort=args.cohort,
            pair_id=args.pair_id,
            arm=args.arm,
        )
    if args.command == "recall":
        query = _ledger_from_args(args).query_for_recall(
            args.incident_id,
            crossover=args.crossover,
        )
        return recall_public(query, base_url=args.base_url)
    if args.command == "finish":
        return _ledger_from_args(args).finish(
            incident_id=args.incident_id,
            first_attempt_passed=args.first_attempt == "passed",
            pre_attempt_recall=args.pre_recall,
            crossover_recall=args.crossover_recall,
            verification=args.verification,
            match_quality=args.match_quality,
            solution_id=args.solution_id,
        )
    return summarize(Path(args.ledger))


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        output = _run_command(args)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
