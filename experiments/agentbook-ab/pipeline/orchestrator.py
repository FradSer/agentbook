#!/usr/bin/env python
"""Single orchestrator: run each cell-sample through the agentic loop, score it
immediately with the tamper-proof core, and write one self-describing
result.json. There is no separate score pass that could read a stale tree.

Usage:
  # smoke: 3 tasks x 1 free model x {control,good} x k=1
  uv run python -m pipeline.orchestrator --smoke --seed --base http://127.0.0.1:8078

  # full: all tasks x panel x {control,good,oracle} x k=3
  uv run python -m pipeline.orchestrator --arms control good oracle -k 3 \
      --day-budget 1000 --base http://127.0.0.1:8078
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from benchmark.agentbook_client import AgentbookClient  # noqa: E402
from benchmark.paths import DEFAULT_MANIFEST, ORACLE, TASKS  # noqa: E402
from harness.agent_loop import run_episode  # noqa: E402
from harness.llm_openrouter import OpenRouterLLM  # noqa: E402
from harness.panel import resolve_panel  # noqa: E402
from harness.prompts import SYSTEM_PROMPT  # noqa: E402
from harness.sandbox import commit_fix, prepare_cell  # noqa: E402
from score import score_run_dir  # noqa: E402

from pipeline.arm_context import build_prompt  # noqa: E402
from pipeline.grid import enumerate_cells  # noqa: E402
from pipeline.provenance import harness_git_commit, prompt_hash, text_hash  # noqa: E402

MEMORIES = ORACLE / "memories.json"


def _meta(iid: str) -> dict:
    return json.loads((TASKS / iid / "META.json").read_text())


def run_cell(cell, llm, client, *, step_budget, temperature, seed_base, bash_timeout):
    meta = _meta(cell.iid)
    repo = prepare_cell(cell.iid, cell.arm, cell.model_slug, cell.sample_idx)
    user_prompt, arm_meta = build_prompt(
        cell.iid,
        cell.arm,
        client=client,
        model_slug=cell.model_slug,
        sample_idx=cell.sample_idx,
    )
    seed = seed_base + cell.sample_idx

    episode = run_episode(
        repo,
        user_prompt,
        llm,
        cell.model,
        step_budget=step_budget,
        temperature=temperature,
        seed=seed,
        bash_timeout=bash_timeout,
        apply_patch=arm_meta.get("apply_patch"),
        verification=arm_meta.get("verification"),
    )
    commit_fix(repo)
    score = score_run_dir(meta, cell.run_dir, arm=cell.arm)
    submitted = bool(score.get("submitted"))
    tests_pass = score.get("tests_pass")
    resolved = bool(submitted and tests_pass)

    result = {
        "instance_id": cell.iid,
        "arm": cell.arm,
        "model": cell.model,
        "model_slug": cell.model_slug,
        "sample_idx": cell.sample_idx,
        "prompt_hash": prompt_hash(SYSTEM_PROMPT, user_prompt),
        "arm_context_hash": text_hash(json.dumps(arm_meta, sort_keys=True)),
        "arm_meta": arm_meta,
        "temperature": temperature,
        "seed": seed,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "harness_git_commit": harness_git_commit(),
        "stop_reason": episode.stop_reason,
        "turns_used": episode.turns_used,
        "submitted": submitted,
        "tests_pass": tests_pass,
        "resolved": resolved,
        "diff_lines": score.get("diff_lines"),
        "score_summary": score.get("summary"),
        "episode_error": episode.error,
    }
    cell.run_dir.mkdir(parents=True, exist_ok=True)
    (cell.run_dir / "transcript.json").write_text(
        json.dumps(episode.to_dict(), indent=2) + "\n"
    )
    cell.result_path.write_text(json.dumps(result, indent=2) + "\n")
    return result


def _has_memory(c, mem_ids: set[str], synth_ids: set[str], loop_ids: set[str]) -> bool:
    """Per-arm memory-prerequisite gate. A cell is dispatched only when its
    iid carries the cache its arm needs.

    `good_rotate` is the union gate: every sub-arm the rotation dispatcher may
    pick (`good`, `good_synth`, `good_loop`, `good_multi_loop`) must be backed
    by data for the iid, otherwise the recursive sub-arm call inside
    `build_prompt` would crash on a missing-cache lookup at runtime.
    """
    if c.arm in ("good", "good_apply"):
        return c.iid in mem_ids
    if c.arm == "good_synth":
        return c.iid in synth_ids
    if c.arm in ("good_loop", "control_loop"):
        # control_loop reuses good_loop's verification cache (no memory block);
        # both need a runnable multi-repro check for the iid.
        return c.iid in loop_ids
    if c.arm == "sibling_loop":
        # needs THIS task's loop repros AND a taxonomy-selected sibling that
        # carries synthesized knowledge to inject.
        from pipeline.arm_context import _taxonomy_sibling

        sib = _taxonomy_sibling(c.iid)
        return c.iid in loop_ids and bool(sib) and sib in synth_ids
    if c.arm == "good_multi_loop":
        # needs BOTH a prose recall AND a multi-repro verification cache
        return c.iid in mem_ids and c.iid in loop_ids
    if c.arm == "good_router":
        # router dispatches across all 4 recall arms; gate on the broadest
        # requirement so every chosen sub-arm has data.
        return c.iid in mem_ids and c.iid in synth_ids
    if c.arm == "good_rotate":
        # rotation may dispatch to ANY runtime sub-arm across samples; require
        # all three sub-arm prerequisites so no sample slot crashes.
        return c.iid in mem_ids and c.iid in synth_ids and c.iid in loop_ids
    return True


def run_chain(
    chain: list,
    llm,
    client,
    *,
    step_budget: int,
    temperature: float,
    seed_base: int,
    bash_timeout: int,
) -> list:
    """Run a per-(iid, model) chain of good_rotate cells serially.

    Sample N writes its result.json before sample N+1's run_cell call, so
    `_load_prior_sample_outcomes(iid, model_slug, N+1)` finds sample N's row on
    disk. No ThreadPoolExecutor inside the chain -- the serial loop is the
    load-bearing invariant for the rotation arm. Cells are run in `sample_idx`
    order regardless of the input list's order so the caller does not need to
    pre-sort.
    """
    ordered = sorted(chain, key=lambda c: c.sample_idx)
    results: list = []
    for cell in ordered:
        res = run_cell(
            cell,
            llm,
            client,
            step_budget=step_budget,
            temperature=temperature,
            seed_base=seed_base,
            bash_timeout=bash_timeout,
        )
        results.append(res)
    return results


def _dispatch_todo(
    todo: list,
    *,
    llm,
    client,
    workers: int,
    step_budget: int,
    temperature: float,
    seed_base: int,
    bash_timeout: int,
    on_result=None,
    on_error=None,
) -> tuple[int, int]:
    """Split scheduling per architecture.md:

      - `good_rotate` cells are grouped into per-`(iid, model)` chains and
        dispatched via `run_chain` -- the in-chain `run_cell` calls execute
        serially so sample N writes `result.json` before sample N+1 reads it.
      - everything else goes through the existing parallel pool.

    Pool A (other_cells) and Pool B (chains) run in parallel: `workers` caps
    chain-level concurrency for rotate AND cell-level concurrency for the rest,
    so the operator's existing `--workers` knob still bounds total in-flight
    LLM calls.

    Callers may pass `on_result(cell, res, dt)` / `on_error(cell, exc, dt)`
    hooks to receive per-cell completions. Returns `(ran, errors)`.
    """
    rotate_cells = [c for c in todo if c.arm == "good_rotate"]
    other_cells = [c for c in todo if c.arm != "good_rotate"]
    chains: dict[tuple[str, str], list] = defaultdict(list)
    for c in rotate_cells:
        chains[(c.iid, c.model)].append(c)
    for chain in chains.values():
        chain.sort(key=lambda c: c.sample_idx)

    def _cell_task(cell):
        t0 = time.time()
        try:
            res = run_cell(
                cell,
                llm,
                client,
                step_budget=step_budget,
                temperature=temperature,
                seed_base=seed_base,
                bash_timeout=bash_timeout,
            )
            return cell, res, time.time() - t0, None
        except Exception as exc:  # noqa: BLE001 -- isolate one cell's failure
            return cell, None, time.time() - t0, exc

    def _chain_task(chain):
        t0 = time.time()
        try:
            results = run_chain(
                chain,
                llm,
                client,
                step_budget=step_budget,
                temperature=temperature,
                seed_base=seed_base,
                bash_timeout=bash_timeout,
            )
            return chain, results, time.time() - t0, None
        except Exception as exc:  # noqa: BLE001 -- isolate one chain's failure
            return chain, None, time.time() - t0, exc

    ran = errors = 0
    with (
        ThreadPoolExecutor(max_workers=max(workers, 1)) as pool_a,
        ThreadPoolExecutor(max_workers=max(workers, 1)) as pool_b,
    ):
        cell_futs = [pool_a.submit(_cell_task, c) for c in other_cells]
        chain_futs = [pool_b.submit(_chain_task, ch) for ch in chains.values()]

        for fut in as_completed(cell_futs):
            cell, res, dt, exc = fut.result()
            ran += 1
            if exc is not None:
                errors += 1
                if on_error is not None:
                    on_error(cell, exc, dt)
            elif on_result is not None:
                on_result(cell, res, dt)

        for fut in as_completed(chain_futs):
            chain, results, dt, exc = fut.result()
            if exc is not None:
                # Whole chain failed: count one error and skip per-cell hooks
                # (the chain's first cell raised; subsequent cells did not run).
                errors += 1
                ran += 1
                if on_error is not None:
                    on_error(chain[0], exc, dt)
                continue
            for cell, res in zip(chain, results, strict=True):
                ran += 1
                if on_result is not None:
                    on_result(cell, res, dt)

    return ran, errors


def main() -> None:
    ap = argparse.ArgumentParser(description="agentbook weak-model A/B orchestrator")
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--arms", nargs="+", default=["control", "good", "oracle"])
    ap.add_argument("--models", nargs="*", default=None, help="default: free panel")
    ap.add_argument("-k", "--samples", type=int, default=3)
    ap.add_argument("--base", default="http://127.0.0.1:8078")
    ap.add_argument("--smoke", action="store_true", help="3 tasks x 1 model x cg x k1")
    ap.add_argument("--max-tasks", type=int, default=None)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--step-budget", type=int, default=40)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--seed-base", type=int, default=1000)
    ap.add_argument("--bash-timeout", type=int, default=120)
    ap.add_argument("--rpm", type=int, default=240, help="req/min ceiling (paid)")
    ap.add_argument("--day-budget", type=int, default=100000, help="daily call cap")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--workers", type=int, default=12, help="concurrent cell episodes")
    ap.add_argument("--allow-paid-fallback", action="store_true")
    ap.add_argument(
        "--provider",
        choices=["openrouter", "ollama", "gemini", "openai_compat"],
        default="openrouter",
        help="LLM backend (ollama = local, no rate limits)",
    )
    ap.add_argument(
        "--base-url",
        default=None,
        help="base URL for --provider openai_compat (default: internal gateway)",
    )
    ap.add_argument(
        "--reasoning-effort",
        default="low",
        choices=["low", "medium", "high"],
        help="gpt-oss reasoning effort (ollama); high = max capability",
    )
    ap.add_argument("--seed", action="store_true", help="seed memories before running")
    ap.add_argument("--force", action="store_true", help="re-run fresh cells")
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text())
    ids = [e["instance_id"] for e in manifest]
    if args.only:
        ids = [i for i in ids if i in set(args.only)]
    arms = list(args.arms)
    if args.provider in ("ollama", "gemini"):
        models = args.models or sys.exit(
            f"--provider {args.provider} requires --models"
        )
    else:
        models = args.models or resolve_panel()
    k = args.samples
    if args.smoke:
        ids = ids[:3]
        models = models[:1]
        arms = [a for a in ("control", "good") if a in arms] or ["control", "good"]
        k = 1
    if args.max_tasks:
        ids = ids[: args.max_tasks]
    if not models:
        sys.exit("no models resolved (panel empty?)")

    print(
        f"cells = {len(ids)} tasks x {arms} x {len(models)} models x k={k} "
        f"= {len(ids) * len(arms) * len(models) * k}"
    )
    print(f"models: {models}")

    client = None
    if "good" in arms:
        client = AgentbookClient(base_url=args.base)
        if args.seed:
            st = client.seed_memories(MEMORIES, include_distractors=True)
            print(
                f"seeded {len(st.get('memories_seeded', []))} memories + "
                f"{len(st.get('distractor_pids', []))} distractors"
            )
        else:
            # good arm reads the offline recall_cache; the live API is only
            # needed on a cache miss, so a down API is non-fatal here.
            try:
                client.ping()
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[warn] agentbook API not reachable ({exc}); "
                    "good arm will rely on the offline recall_cache."
                )

    if args.provider == "openai_compat":
        from harness.llm_openai_compat import OpenAICompatLLM

        llm = OpenAICompatLLM(
            base_url=args.base_url, rpm=args.rpm, max_tokens=args.max_tokens
        )
    elif args.provider == "gemini":
        from harness.llm_gemini import GeminiLLM

        llm = GeminiLLM(
            rpm=args.rpm, day_cap=args.day_budget, max_tokens=args.max_tokens
        )
    elif args.provider == "ollama":
        from harness.llm_ollama import OllamaLLM

        llm = OllamaLLM(
            max_tokens=args.max_tokens, reasoning_effort=args.reasoning_effort
        )
    else:
        llm = OpenRouterLLM(
            rpm=args.rpm,
            day_cap=args.day_budget,
            max_tokens=args.max_tokens,
            allow_paid_fallback=args.allow_paid_fallback,
        )

    # k applies to control/good; oracle is a single-sample ceiling.
    def k_for(arm: str) -> int:
        return 1 if arm == "oracle" else k

    # task-major ordering: emit every arm for one task before the next task, so
    # paired control/good/oracle data completes per task early (incremental
    # signal + robustness to a mid-run free-tier daily cap).
    cells = []
    for iid in ids:
        for arm in arms:
            cells.extend(enumerate_cells([iid], [arm], models, k_for(arm)))
    # good arm only where a memory exists (recall cache); elsewhere it would just
    # equal control (no useful hint), so skip those cells. good_synth is gated on
    # its own synthesized-knowledge cache.
    from pipeline.arm_context import RECALL_CACHE, SYNTH_CACHE

    mem_ids = (
        set(json.loads(RECALL_CACHE.read_text())) if RECALL_CACHE.exists() else set()
    )
    synth = json.loads(SYNTH_CACHE.read_text()) if SYNTH_CACHE.exists() else {}
    synth_ids = set(synth)
    # good_loop additionally needs a runnable verification check for that task.
    loop_ids = {i for i, e in synth.items() if e.get("verification_feasible")}

    cells = [c for c in cells if _has_memory(c, mem_ids, synth_ids, loop_ids)]
    todo = [c for c in cells if args.force or not c.is_fresh()]
    done = len(cells) - len(todo)
    print(f"todo {len(todo)} cells ({done} already fresh) | {args.workers} workers")

    # warm process-global caches before fanning out (avoid first-call races)
    if "oracle" in arms and ids:
        from pipeline.arm_context import _oracle_entry

        _oracle_entry(ids[0])
    if (
        {"good_synth", "good_loop", "good_multi_loop", "control_loop"} & set(arms)
    ) and ids:
        from pipeline.arm_context import _synth_entry

        _synth_entry(ids[0])
    harness_git_commit()

    progress = {"i": 0}

    def _on_result(cell, res, dt):
        progress["i"] += 1
        print(
            f"  [{progress['i']}/{len(todo)}] {cell.dirname}: "
            f"resolved={res['resolved']} submitted={res['submitted']} "
            f"stop={res['stop_reason']} turns={res['turns_used']} ({dt:.0f}s)",
            flush=True,
        )

    def _on_error(cell, exc, dt):
        progress["i"] += 1
        print(
            f"  [{progress['i']}/{len(todo)}] {cell.dirname}: ERROR {exc}",
            flush=True,
        )

    ran, errors = _dispatch_todo(
        todo,
        llm=llm,
        client=client,
        workers=args.workers,
        step_budget=args.step_budget,
        temperature=args.temperature,
        seed_base=args.seed_base,
        bash_timeout=args.bash_timeout,
        on_result=_on_result,
        on_error=_on_error,
    )

    if client:
        client.close()
    llm.close()
    print(f"\nran {ran} cells ({errors} errored); {done} already fresh.")
    print("results under runs_v2/; aggregate with: uv run python -m stats.aggregate")


if __name__ == "__main__":
    main()
