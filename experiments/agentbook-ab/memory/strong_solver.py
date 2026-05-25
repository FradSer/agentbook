#!/usr/bin/env python
"""Run an independent strong solver (`claude -p`, headless) on each task.

The solver works in a copy of `tasks/<id>/repo` placed OUTSIDE the agentbook
source tree (so Claude Code does not auto-discover the project CLAUDE.md), with
no `_oracle/` content and no hidden grading test on disk. Its source edits are
committed as "agent fix" and its final narrative saved to `solution.md`. A run
becomes a `good` memory only if it later PASSES (see verify_solution.py).

Usage:
  uv run python -m memory.strong_solver --max-tasks 3 --model sonnet
  uv run python -m memory.strong_solver --model sonnet            # all tasks
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from benchmark.paths import DEFAULT_MANIFEST, ORACLE, TASKS  # noqa: E402
from cell_workspace import has_agent_fix, prepare_run_dir  # noqa: E402

CLAUDE_BIN = Path(os.path.expanduser("~/.local/bin/claude"))
SOLVER_ROOT = Path(tempfile.gettempdir()) / "agentbook-ab-solver"
SOLVER_RECORDS = ORACLE / "solver_runs.json"

# The `claude` shell function unsets these before invoking the real binary so the
# default subscription/OAuth credentials are used. We replicate that here.
_PROVIDER_ENV = (
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
)

SOLVER_PROMPT = """You are an expert engineer fixing a real bug in the sympy \
source tree located at your current working directory.

{bug}

Constraints:
- Edit only sympy SOURCE files. Do NOT create or edit any file under a tests/ \
directory, and do not write new test files.
- Do not use the internet.
- Make the smallest correct change that fixes the described behavior.

When you are done, end your final message with exactly this three-line summary \
(plain prose, NO code blocks, NO diff):
ROOT CAUSE: <module/function that is wrong and why>
FIX: <what you changed, conceptually>
STEPS: <numbered steps another engineer would follow to reproduce and apply it>
"""


def _solver_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in _PROVIDER_ENV:
        env.pop(key, None)
    return env


def _commit_fix(repo: Path) -> bool:
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, timeout=60)
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    if not status:
        return False
    subprocess.run(
        ["git", "commit", "-q", "-m", "agent fix"],
        cwd=repo,
        capture_output=True,
        timeout=60,
    )
    return has_agent_fix(repo)


def run_solver(iid: str, *, model: str, budget_usd: float | None, timeout: int) -> dict:
    bug = (TASKS / iid / "BUG.md").read_text()
    run_repo = prepare_run_dir(iid, "solver", runs_dir=SOLVER_ROOT)
    run_dir = run_repo.parent
    prompt = SOLVER_PROMPT.format(bug=bug)

    cmd = [
        str(CLAUDE_BIN),
        "-p",
        prompt,
        "--output-format",
        "json",
        "--dangerously-skip-permissions",
        "--no-session-persistence",
        "--model",
        model,
        "--disallowedTools",
        "WebSearch",
        "WebFetch",
    ]
    if budget_usd:
        cmd += ["--max-budget-usd", str(budget_usd)]

    t0 = time.time()
    record: dict = {"instance_id": iid, "model": model}
    try:
        r = subprocess.run(
            cmd,
            cwd=run_repo,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_solver_env(),
        )
    except subprocess.TimeoutExpired:
        record.update(error="timeout", submitted=False, solution_path=None)
        return record

    record["elapsed_s"] = round(time.time() - t0, 1)
    result_text = ""
    try:
        payload = json.loads(r.stdout)
        result_text = payload.get("result") or ""
        record["num_turns"] = payload.get("num_turns")
        record["cost_usd"] = payload.get("total_cost_usd")
        record["is_error"] = payload.get("is_error")
    except json.JSONDecodeError:
        record["error"] = f"non-json output (rc={r.returncode}): {r.stderr[:200]}"
        result_text = r.stdout

    (run_dir / "solution.md").write_text(result_text or "")
    record["submitted"] = _commit_fix(run_repo)
    record["solution_path"] = str(run_dir / "solution.md")
    return record


def main() -> None:
    ap = argparse.ArgumentParser(description="Strong-solver memory generation")
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--model", default="sonnet", help="claude model alias or id")
    ap.add_argument("--max-tasks", type=int, default=None)
    ap.add_argument("--budget-usd", type=float, default=None, help="per-task cap")
    ap.add_argument("--timeout", type=int, default=900, help="per-task seconds")
    ap.add_argument("--only", nargs="*", default=None, help="specific instance ids")
    ap.add_argument(
        "--redo", action="store_true", help="re-solve tasks already submitted"
    )
    ap.add_argument(
        "--workers", type=int, default=6, help="concurrent claude -p solvers"
    )
    args = ap.parse_args()

    if not CLAUDE_BIN.exists():
        sys.exit(f"claude binary not found at {CLAUDE_BIN}")

    manifest = json.loads(args.manifest.read_text())
    ids = [e["instance_id"] for e in manifest]
    if args.only:
        ids = [i for i in ids if i in set(args.only)]
    if args.max_tasks:
        ids = ids[: args.max_tasks]

    SOLVER_ROOT.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    if SOLVER_RECORDS.exists():
        records = json.loads(SOLVER_RECORDS.read_text())
    by_id = {r["instance_id"]: r for r in records}

    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    todo = [iid for iid in ids if args.redo or not by_id.get(iid, {}).get("submitted")]
    print(f"solving {len(todo)}/{len(ids)} tasks with {args.workers} parallel workers")
    lock = threading.Lock()

    def work(iid: str) -> tuple[str, dict]:
        rec = run_solver(
            iid, model=args.model, budget_usd=args.budget_usd, timeout=args.timeout
        )
        with lock:
            by_id[iid] = rec
            SOLVER_RECORDS.write_text(json.dumps(list(by_id.values()), indent=2) + "\n")
        return iid, rec

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(work, iid): iid for iid in todo}
        for fut in as_completed(futs):
            iid, rec = fut.result()
            done += 1
            print(
                f"[{done}/{len(todo)}] {iid}: submitted={rec.get('submitted')} "
                f"turns={rec.get('num_turns')} cost=${rec.get('cost_usd')} "
                f"{rec.get('error', '')}",
                flush=True,
            )

    print(f"\nsolver records -> {SOLVER_RECORDS}")


if __name__ == "__main__":
    main()
