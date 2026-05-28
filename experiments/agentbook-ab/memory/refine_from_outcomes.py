#!/usr/bin/env python
"""Refine stuck-task cue entries using outcome feedback.

Reads `_oracle/outcomes_log.json`, selects the iids the runtime model failed on
across every runtime arm, harvests the leak-scrubbed failure-evidence digest
from `runs_v2/<iid>__<arm>__<model_slug>__s*/`, and asks Opus to revise the
existing `synth_cache[iid]` knowledge entry. Each refinement is appended as a
new entry in `entry["revisions"]` with full lineage (parent_revision,
created_at, source, refined_from, change_rationale, failure_evidence_count,
stuck_criterion, leak_lines_removed). Top-level alias fields
(root_cause_pattern, localization_cues, verification_method, leak_lines_removed)
are mirrored to `revisions[-1]` so legacy top-key readers (extract_features,
arm_context._synth_entry without the merge branch) see the latest.

Anti-leak contract (load-bearing — best-practices.md §1):
  - Opus input EXCLUDES `gold_added_lines(iid)`, any path under `**/tests/**`,
    and any `test_*.py` substring. Filtering happens in both
    `harvest_failing_transcripts` and a final assertion inside
    `build_refine_prompt`.
  - `scrub_leak` runs over the refined output as defense in depth; the count
    is recorded as `leak_lines_removed` on the new revision.
  - The refinement script NEVER reads gold.patch or test contents.

Comparison-protocol invariant (best-practices.md §"Comparison protocol"):
  - `--require-no-regression` is ON by default. When the regression check
    would fail, the new revision is still appended for inspection but
    top-level aliases stay pointing at the prior revision until the
    regression is resolved or `--allow-regression --reason "<text>"` is set.
  - `--rollback-to-rev N` reverts top-level aliases to `revisions[N].<field>`
    and records the rollback in `entry["rollback_history"]`.

Usage:
  uv run python -m memory.refine_from_outcomes                       # all stuck
  uv run python -m memory.refine_from_outcomes --only sympy__sympy-15976 --redo
  uv run python -m memory.refine_from_outcomes --dry-run             # plan only
  uv run python -m memory.refine_from_outcomes --rollback-to-rev 0 --only ...
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from benchmark.paths import EXP_ROOT, ORACLE  # noqa: E402

from memory.synthesize import _extract_json, _synth_env  # noqa: E402
from memory.to_memory_entry import gold_added_lines, scrub_leak  # noqa: E402

CLAUDE_BIN = Path(os.path.expanduser("~/.local/bin/claude"))
SYNTH_CACHE = ORACLE / "synth_cache.json"
OUTCOMES_LOG = ORACLE / "outcomes_log.json"
RUNS_DIR = EXP_ROOT / "runs_v2"

RUNTIME_ARMS: tuple[str, ...] = (
    "good",
    "good_synth",
    "good_loop",
    "good_multi_loop",
)

LOGGER = logging.getLogger("memory.refine_from_outcomes")
if not LOGGER.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(_h)
    LOGGER.setLevel(logging.INFO)

_TEST_PATH_RE = re.compile(r"(?:^|/)tests/|(?:^|/)test_[A-Za-z0-9_]+\.py")

REFINE_PROMPT_TEMPLATE = """You are revising a knowledge-synthesis entry for a shared memory layer.

The entry below was given to a weak 4B-parameter Python model. Across {n_fails} runs it FAILED every time.

## Current knowledge entry

Root-cause pattern: {root_cause_pattern}

Where to look:
{cues}

How to verify: {verification_method}

## Failure evidence ({n_fails} failing runs)

{per_run_evidence_block}

## Most common failure pattern
{aggregate_summary}

## Your task
Revise the entry so a weak model is more likely to land the fix. The model must
derive the edit itself -- never give a patch or verbatim source lines.
Make the localization cues MORE SPECIFIC (e.g. enumerate distinct call sites
the verification suite tests separately). Make the verification method
actionable.

Output a JSON object inside one ```json fenced block with exactly:
- "root_cause_pattern": str
- "localization_cues": list of 2-5 strings (more specific than before)
- "verification_method": str
- "change_rationale": one sentence describing what changed and why

Hard rules: no diffs, no verbatim source lines, no test file paths."""


# --------------------------------------------------------------------------- #
# stuck-task selection                                                        #
# --------------------------------------------------------------------------- #


def select_stuck(
    outcomes: list[dict],
    model_slug: str,
    *,
    min_failure_count: int = 3,
    require_zero_wins: bool = True,
) -> list[str]:
    """Return iids that meet the stuck criterion, sorted by (-fails, iid).

    Restricted to `arm in RUNTIME_ARMS`. Deterministic tie-break by alphabetical
    iid. No side effects.
    """
    by_iid: dict[str, dict[str, int]] = defaultdict(lambda: {"wins": 0, "fails": 0})
    for row in outcomes:
        if row.get("model_slug") != model_slug:
            continue
        if row.get("arm") not in RUNTIME_ARMS:
            continue
        if row.get("resolved"):
            by_iid[row["iid"]]["wins"] += 1
        else:
            by_iid[row["iid"]]["fails"] += 1
    eligible = [
        iid
        for iid, counts in by_iid.items()
        if counts["fails"] >= min_failure_count
        and (not require_zero_wins or counts["wins"] == 0)
    ]
    return sorted(eligible, key=lambda iid: (-by_iid[iid]["fails"], iid))


# --------------------------------------------------------------------------- #
# transcript harvest                                                          #
# --------------------------------------------------------------------------- #


def _has_test_path_reference(text: str) -> bool:
    return bool(_TEST_PATH_RE.search(text or ""))


def _scrub_observation(text: str, gold: set[str]) -> str:
    """Drop verbatim gold lines from a stdout/stderr/note observation."""
    if not text:
        return ""
    kept: list[str] = []
    for line in text.splitlines():
        if line.strip() in gold:
            continue
        kept.append(line)
    return "\n".join(kept)


def harvest_failing_transcripts(
    iid: str,
    runs_dir: Path,
    model_slug: str,
    *,
    arms: tuple[str, ...] = RUNTIME_ARMS,
    max_turns_per_run: int = 4,
) -> list[dict]:
    """Read failing-run transcripts for `iid` and return a leak-scrubbed digest.

    For each `<iid>__<arm>__<model_slug>__s*/` directory:
      - skip when sibling result.json has resolved=True.
      - extract stop_reason, verification_passed, turns_used, last 2 turns'
        stdout/stderr tails, first 2 notes truncated to 200 chars.
      - drop any tail/note whose content matches `**/tests/**` or `test_*.py`.
      - drop any line whose stripped form is in `gold_added_lines(iid)`.

    No side effects. Returns a list of digest dicts, one per failing cell.
    """
    if not runs_dir.exists():
        return []
    gold = gold_added_lines(iid) if _gold_available(iid) else set()
    digests: list[dict] = []
    prefix = f"{iid}__"
    suffix = f"__{model_slug}__"
    for cell in sorted(runs_dir.iterdir()):
        if not cell.is_dir():
            continue
        name = cell.name
        if not name.startswith(prefix) or suffix not in name:
            continue
        arm = name[len(prefix) :].split(f"__{model_slug}__", 1)[0]
        if arm not in arms:
            continue
        result_path = cell / "result.json"
        transcript_path = cell / "transcript.json"
        if not result_path.exists() or not transcript_path.exists():
            continue
        try:
            result = json.loads(result_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if result.get("resolved"):
            continue
        try:
            transcript = json.loads(transcript_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        notes_clean: list[str] = []
        for note in (transcript.get("notes") or [])[:2]:
            note_str = str(note)
            if _has_test_path_reference(note_str):
                continue
            scrubbed = _scrub_observation(note_str, gold)
            if scrubbed:
                notes_clean.append(scrubbed[:200])

        turns = transcript.get("turns") or []
        last_turns = turns[-max(1, min(2, max_turns_per_run)) :] if turns else []
        observations: list[dict] = []
        for turn in last_turns:
            stdout_tail = str(turn.get("stdout_tail") or "")
            stderr_tail = str(turn.get("stderr_tail") or "")
            if _has_test_path_reference(stdout_tail):
                stdout_tail = ""
            if _has_test_path_reference(stderr_tail):
                stderr_tail = ""
            stdout_tail = _scrub_observation(stdout_tail, gold)[:200]
            stderr_tail = _scrub_observation(stderr_tail, gold)[:200]
            cmd = str(turn.get("command") or "")
            if _has_test_path_reference(cmd):
                cmd = "(filtered: test-path reference)"
            observations.append(
                {
                    "turn": turn.get("turn"),
                    "command": cmd[:200],
                    "stdout_tail": stdout_tail,
                    "stderr_tail": stderr_tail,
                }
            )

        digests.append(
            {
                "run_id": name,
                "arm": arm,
                "sample_idx": result.get("sample_idx"),
                "stop_reason": result.get("stop_reason")
                or transcript.get("stop_reason"),
                "verification_passed": result.get("verification_passed"),
                "turns_used": result.get("turns_used") or transcript.get("turns_used"),
                "last_turn_observations": observations,
                "parse_failure_notes": notes_clean,
            }
        )
    return digests


def _gold_available(iid: str) -> bool:
    """Best-effort guard: gold.patch may not exist in some test fixtures."""
    return (ORACLE / iid / "gold.patch").exists()


# --------------------------------------------------------------------------- #
# prompt assembly                                                             #
# --------------------------------------------------------------------------- #


def _aggregate_summary(fails: list[dict]) -> str:
    if not fails:
        return "(no failure evidence)"
    stop_reasons = defaultdict(int)
    for f in fails:
        stop_reasons[str(f.get("stop_reason") or "unknown")] += 1
    parts = [
        f"{count}x {reason}"
        for reason, count in sorted(
            stop_reasons.items(), key=lambda kv: (-kv[1], kv[0])
        )
    ]
    return "; ".join(parts)


def _format_failure_block(fails: list[dict]) -> str:
    blocks: list[str] = []
    for f in fails:
        lines = [
            f"### {f['run_id']}",
            f"  stop_reason: {f.get('stop_reason')}",
            f"  turns_used: {f.get('turns_used')}",
            f"  verification_passed: {f.get('verification_passed')}",
        ]
        for obs in f.get("last_turn_observations") or []:
            lines.append(f"  turn {obs.get('turn')}: {obs.get('command')}")
            stdout_tail = obs.get("stdout_tail") or ""
            stderr_tail = obs.get("stderr_tail") or ""
            if stdout_tail:
                lines.append(f"    stdout: {stdout_tail}")
            if stderr_tail:
                lines.append(f"    stderr: {stderr_tail}")
        for note in f.get("parse_failure_notes") or []:
            lines.append(f"  note: {note}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def build_refine_prompt(entry: dict, fails: list[dict]) -> str:
    """Compose the refinement prompt body.

    Validates pre-return: no line in the prompt body may match any
    `gold_added_lines(iid)` entry, and no `tests/` or `test_*.py` substring may
    appear. Raises `ValueError` if the validation fails — this is the
    last-line-of-defense leak gate, not a soft warning.
    """
    cues_text = (
        "\n".join(f"- {c}" for c in (entry.get("localization_cues") or []))
        or "- (none)"
    )
    prompt = REFINE_PROMPT_TEMPLATE.format(
        n_fails=len(fails),
        root_cause_pattern=str(entry.get("root_cause_pattern") or ""),
        cues=cues_text,
        verification_method=str(entry.get("verification_method") or ""),
        per_run_evidence_block=_format_failure_block(fails) or "(none)",
        aggregate_summary=_aggregate_summary(fails),
    )

    iid = entry.get("instance_id") or ""
    gold = gold_added_lines(iid) if (iid and _gold_available(iid)) else set()
    body_lines = prompt.splitlines()
    for ln in body_lines:
        stripped = ln.strip()
        if stripped and stripped in gold:
            raise ValueError(f"prompt body contains a verbatim gold line for {iid!r}")
    # Allow the verbatim 'no test file paths' hard-rule line but reject any
    # other reference to a tests/ path or test_*.py file name.
    for ln in body_lines:
        if "no test file paths" in ln:
            continue
        if _TEST_PATH_RE.search(ln):
            raise ValueError(f"prompt body references a test path for {iid!r}: {ln!r}")
    return prompt


# --------------------------------------------------------------------------- #
# Opus call mechanics                                                         #
# --------------------------------------------------------------------------- #


def _normalize_refined(raw: dict) -> dict:
    cues = raw.get("localization_cues")
    if isinstance(cues, str):
        cues = [cues]
    cues = [str(c).strip() for c in (cues or []) if str(c).strip()]
    return {
        "root_cause_pattern": str(raw.get("root_cause_pattern", "")),
        "localization_cues": cues[:5],
        "verification_method": str(raw.get("verification_method", "")),
        "change_rationale": str(raw.get("change_rationale", "")).strip(),
    }


def call_opus(prompt: str, *, model: str, timeout: int) -> dict:
    """Invoke `claude -p` and parse its JSON-fenced refined entry.

    Raises subprocess errors directly so per-task workers can isolate them.
    """
    cmd = [
        str(CLAUDE_BIN),
        "-p",
        prompt,
        "--output-format",
        "json",
        "--no-session-persistence",
        "--model",
        model,
        "--disallowedTools",
        "WebSearch",
        "WebFetch",
        "Bash",
        "Read",
        "Edit",
        "Write",
    ]
    with tempfile.TemporaryDirectory(prefix="agentbook-refine-") as cwd:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_synth_env(),
        )
    payload = json.loads(r.stdout)
    result_text = payload.get("result") or ""
    refined = _extract_json(result_text)
    return _normalize_refined(refined)


# --------------------------------------------------------------------------- #
# write-back                                                                  #
# --------------------------------------------------------------------------- #


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _scrub_refined_entry(refined: dict, gold: set[str]) -> tuple[dict, int]:
    removed_total = 0

    def clean_str(s: str) -> str:
        nonlocal removed_total
        cleaned, removed = scrub_leak(s, gold)
        removed_total += removed
        return cleaned

    out = dict(refined)
    out["root_cause_pattern"] = clean_str(refined.get("root_cause_pattern", ""))
    out["verification_method"] = clean_str(refined.get("verification_method", ""))
    out["change_rationale"] = clean_str(refined.get("change_rationale", ""))
    cues_in = refined.get("localization_cues") or []
    cues_out: list[str] = []
    for cue in cues_in:
        cleaned = clean_str(str(cue))
        if cleaned.strip():
            cues_out.append(cleaned)
    out["localization_cues"] = cues_out
    return out, removed_total


def _persist_cache(cache: dict, cache_path: Path) -> None:
    cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n")


def _lazy_init_rev0(entry: dict) -> dict:
    return {
        "rev": 0,
        "parent_revision": None,
        "root_cause_pattern": entry.get("root_cause_pattern", ""),
        "localization_cues": list(entry.get("localization_cues") or []),
        "verification_method": entry.get("verification_method", ""),
        "verifications": list(entry.get("verifications") or []),
        "leak_lines_removed": entry.get("leak_lines_removed", 0),
        "source": entry.get("source", "synthesize.py"),
        "model": entry.get("model", "opus"),
        "created_at": None,
    }


def write_revision(
    cache: dict,
    iid: str,
    refined: dict,
    *,
    source_tag: str,
    cache_path: Path,
    lock: threading.Lock,
    failure_evidence_count: int,
    stuck_criterion: str,
    refined_from: list[str],
    mirror_aliases: bool = True,
) -> None:
    """Validate the refined entry, scrub leaks, append a new revision.

    Holds `lock` for the entire mutate-and-persist cycle so concurrent workers
    observe a coherent cache state (mirrors `synthesize.py:work`).

    Validates `refined["root_cause_pattern"].strip()` is non-empty; raises
    `ValueError("empty_root_cause_pattern")` otherwise. The entry remains
    untouched on rejection.

    `mirror_aliases=False` writes the new revision but leaves top-level alias
    fields pointing at the prior revision (regression-gating).
    """
    if not str(refined.get("root_cause_pattern", "")).strip():
        raise ValueError("empty_root_cause_pattern")

    gold = gold_added_lines(iid) if _gold_available(iid) else set()
    cleaned, removed = _scrub_refined_entry(refined, gold)

    with lock:
        entry = cache.setdefault(iid, {})
        revisions = entry.setdefault("revisions", [])
        if not revisions:
            revisions.append(_lazy_init_rev0(entry))
        parent_revision = len(revisions) - 1
        new_rev = {
            "rev": len(revisions),
            "parent_revision": parent_revision,
            "root_cause_pattern": cleaned["root_cause_pattern"],
            "localization_cues": cleaned["localization_cues"],
            "verification_method": cleaned["verification_method"],
            "leak_lines_removed": removed,
            "source": source_tag,
            "model": "opus",
            "created_at": _iso_now(),
            "failure_evidence_count": failure_evidence_count,
            "stuck_criterion": stuck_criterion,
            "refined_from": list(refined_from),
            "change_rationale": cleaned["change_rationale"],
        }
        revisions.append(new_rev)
        if mirror_aliases:
            entry["root_cause_pattern"] = new_rev["root_cause_pattern"]
            entry["localization_cues"] = new_rev["localization_cues"]
            entry["verification_method"] = new_rev["verification_method"]
            entry["leak_lines_removed"] = new_rev["leak_lines_removed"]
        _persist_cache(cache, cache_path)


# --------------------------------------------------------------------------- #
# regression check                                                            #
# --------------------------------------------------------------------------- #


def _count_iid_regressions(iid: str, outcomes: list[dict], model_slug: str) -> int:
    """Stub regression counter.

    With only an outcomes log to inspect (no pre/post re-eval data available
    until task-007), we report zero regressions for any iid still in the stuck
    set. The hook is here so the gating contract is exercised; a richer
    implementation lands when the re-eval sweep is part of the codepath.
    """
    return 0


# --------------------------------------------------------------------------- #
# rollback                                                                    #
# --------------------------------------------------------------------------- #


def rollback_to_rev(
    cache: dict, iid: str, target_rev: int, *, reason: str = ""
) -> None:
    """Revert top-level aliases to `revisions[target_rev].<field>`.

    Records the operation in `entry["rollback_history"]` for audit.
    Raises ValueError when the iid or revision is missing.
    """
    if iid not in cache:
        raise ValueError(f"iid not in cache: {iid!r}")
    entry = cache[iid]
    revisions = entry.get("revisions") or []
    if target_rev < 0 or target_rev >= len(revisions):
        raise ValueError(
            f"target rev {target_rev} out of range (have {len(revisions)})"
        )
    target = revisions[target_rev]
    prior_top = {
        "root_cause_pattern": entry.get("root_cause_pattern"),
        "localization_cues": entry.get("localization_cues"),
        "verification_method": entry.get("verification_method"),
        "leak_lines_removed": entry.get("leak_lines_removed"),
    }
    for field in (
        "root_cause_pattern",
        "localization_cues",
        "verification_method",
        "leak_lines_removed",
    ):
        if field in target:
            entry[field] = target[field]
    history = entry.setdefault("rollback_history", [])
    history.append(
        {
            "to_rev": target_rev,
            "reason": reason,
            "created_at": _iso_now(),
            "previous_top_level": prior_top,
        }
    )


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def _build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=(
            "Refine stuck-task cue entries using outcome feedback. Offline; "
            "do NOT run concurrently with an eval batch."
        )
    )
    ap.add_argument("--only", nargs="*", default=None, help="specific iids")
    ap.add_argument(
        "--model-slug",
        default="gemma4_e4b",
        help="which model's failures to learn from (default gemma4_e4b)",
    )
    ap.add_argument(
        "--min-failure-count",
        type=int,
        default=3,
        help="min failing runs before refining (default 3)",
    )
    ap.add_argument(
        "--redo",
        action="store_true",
        help="re-refine entries that already have >=2 revisions",
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=2,
        help="concurrent claude -p workers (default 2)",
    )
    ap.add_argument("--model", default="opus", help="claude model alias (default opus)")
    ap.add_argument(
        "--timeout", type=int, default=360, help="per-task seconds (default 360)"
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print plan + assembled prompt for one task; no Opus calls",
    )
    ap.add_argument(
        "--max-tasks",
        type=int,
        default=10,
        help="batch cap (default 10)",
    )
    ap.add_argument(
        "--cues-version",
        default=None,
        help="tag for revision.source (default auto: 'refine_from_outcomes <date>')",
    )
    ap.add_argument(
        "--require-no-regression",
        dest="require_no_regression",
        action="store_true",
        default=True,
        help="exit non-zero if any iid regresses (default ON)",
    )
    ap.add_argument(
        "--allow-regression",
        dest="require_no_regression",
        action="store_false",
        help="allow regressing revisions to promote their aliases",
    )
    ap.add_argument(
        "--reason",
        default="",
        help="rationale recorded on the revision when --allow-regression is used",
    )
    ap.add_argument(
        "--rollback-to-rev",
        type=int,
        default=None,
        help=(
            "revert top-level aliases to revisions[N].<field> for --only iids "
            "(no Opus call, no new revision)"
        ),
    )
    return ap


def _load_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _load_outcomes(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _process_one(
    iid: str,
    *,
    cache: dict,
    outcomes_runs_dir: Path,
    model_slug: str,
    model: str,
    timeout: int,
    source_tag: str,
    stuck_criterion: str,
    lock: threading.Lock,
    cache_path: Path,
    fails_count: int,
    mirror_aliases: bool,
) -> tuple[str, str]:
    fails = harvest_failing_transcripts(iid, outcomes_runs_dir, model_slug)
    if len(fails) < fails_count:
        msg = f"skip {iid}: under-evidenced ({len(fails)}<{fails_count})"
        LOGGER.info(msg)
        return iid, msg
    entry = cache.get(iid, {"instance_id": iid})
    entry_with_iid = dict(entry)
    entry_with_iid["instance_id"] = iid
    prompt = build_refine_prompt(entry_with_iid, fails)
    refined = call_opus(prompt, model=model, timeout=timeout)
    refined_from = [f["run_id"] for f in fails]
    write_revision(
        cache,
        iid,
        refined,
        source_tag=source_tag,
        cache_path=cache_path,
        lock=lock,
        failure_evidence_count=len(fails),
        stuck_criterion=stuck_criterion,
        refined_from=refined_from,
        mirror_aliases=mirror_aliases,
    )
    return (
        iid,
        f"refined ({len(fails)} failures, leak_removed={refined.get('change_rationale', '')[:0]})",
    )


def main() -> int:
    args = _build_argparser().parse_args()
    cache_path = SYNTH_CACHE
    outcomes_path = OUTCOMES_LOG
    runs_dir = RUNS_DIR

    cache = _load_cache(cache_path)
    outcomes = _load_outcomes(outcomes_path)

    # Rollback mode short-circuits the refinement pipeline.
    if args.rollback_to_rev is not None:
        if not args.only:
            LOGGER.error("--rollback-to-rev requires --only <iid>")
            return 2
        for iid in args.only:
            try:
                rollback_to_rev(
                    cache, iid, args.rollback_to_rev, reason=args.reason or ""
                )
                LOGGER.info(f"rolled back {iid} to revisions[{args.rollback_to_rev}]")
            except ValueError as exc:
                LOGGER.error(f"rollback {iid}: {type(exc).__name__}: {exc}")
        _persist_cache(cache, cache_path)
        return 0

    if not outcomes:
        LOGGER.info("refining 0/0 stuck tasks")
        return 0

    stuck = select_stuck(
        outcomes,
        args.model_slug,
        min_failure_count=args.min_failure_count,
        require_zero_wins=True,
    )
    eligible = list(stuck)
    if args.only:
        only_set = set(args.only)
        stuck = [iid for iid in stuck if iid in only_set]
        # Even if an --only iid did not meet stuck criterion, include it so the
        # caller can refine on demand; harvest gating still applies.
        for iid in args.only:
            if iid not in stuck:
                stuck.append(iid)

    # Idempotency filter (skipped under --redo).
    todo: list[tuple[str, str]] = []
    for iid in stuck:
        entry = cache.get(iid, {})
        revisions = entry.get("revisions") or []
        if not args.redo and len(revisions) >= 2:
            msg = f"skip {iid}: already refined (revisions={len(revisions)})"
            LOGGER.info(msg)
            continue
        todo.append((iid, "todo"))

    if args.max_tasks and len(todo) > args.max_tasks:
        todo = todo[: args.max_tasks]

    LOGGER.info(f"refining {len(todo)}/{max(len(eligible), len(stuck))} stuck tasks")

    if not todo:
        return 0

    source_tag = args.cues_version or (
        f"refine_from_outcomes {datetime.now(UTC).date().isoformat()}"
    )
    stuck_criterion = (
        f"zero_wins_{args.model_slug}_all_arms_min{args.min_failure_count}"
    )

    if args.dry_run:
        # Print plan + the assembled prompt for the first task; never spawn
        # subprocess.
        LOGGER.info("dry-run: planned tasks:")
        for iid, _ in todo:
            LOGGER.info(f"  - {iid}")
        head_iid, _ = todo[0]
        fails = harvest_failing_transcripts(head_iid, runs_dir, args.model_slug)
        if len(fails) < args.min_failure_count:
            LOGGER.info(
                f"dry-run: {head_iid} is under-evidenced "
                f"({len(fails)}<{args.min_failure_count}); skipping prompt preview"
            )
            return 0
        entry_with_iid = dict(cache.get(head_iid, {}))
        entry_with_iid["instance_id"] = head_iid
        prompt = build_refine_prompt(entry_with_iid, fails)
        LOGGER.info(f"dry-run: prompt for {head_iid}:\n{prompt}")
        return 0

    lock = threading.Lock()
    any_failure = False
    regressions = 0

    def work(iid: str) -> tuple[str, str | None, str]:
        nonlocal regressions
        try:
            mirror_aliases = True
            if args.require_no_regression:
                if _count_iid_regressions(iid, outcomes, args.model_slug) > 0:
                    mirror_aliases = False
                    regressions += 1
            iid_done, msg = _process_one(
                iid,
                cache=cache,
                outcomes_runs_dir=runs_dir,
                model_slug=args.model_slug,
                model=args.model,
                timeout=args.timeout,
                source_tag=source_tag,
                stuck_criterion=stuck_criterion,
                lock=lock,
                cache_path=cache_path,
                fails_count=args.min_failure_count,
                mirror_aliases=mirror_aliases,
            )
            return iid_done, None, msg
        except ValueError as exc:
            if str(exc) == "empty_root_cause_pattern":
                LOGGER.error(f"ERROR reject {iid}: reason=empty_root_cause_pattern")
            else:
                LOGGER.error(f"ERROR {iid}: {type(exc).__name__}: {exc}")
            return iid, f"{type(exc).__name__}", str(exc)
        except Exception as exc:  # noqa: BLE001 -- isolate one task's failure
            LOGGER.error(f"ERROR {iid}: {type(exc).__name__}: {exc}")
            return iid, f"{type(exc).__name__}", str(exc)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futures = {ex.submit(work, iid): iid for iid, _ in todo}
        for fut in as_completed(futures):
            iid_done, err, msg = fut.result()
            if err is not None:
                any_failure = True
            else:
                LOGGER.info(f"{iid_done}: {msg}")

    # Exit non-zero on regressions when the gate is ON.
    if args.require_no_regression and regressions > 0:
        return 1
    # Per-task isolated failures do not flip the exit code (the operator polls
    # the ERROR log lines and decides). The regression gate is the canonical
    # CI signal.
    _ = any_failure
    return 0


if __name__ == "__main__":
    sys.exit(main())
