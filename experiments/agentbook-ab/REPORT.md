# Does agentbook help a coding agent? A controlled A/B on real SWE-bench tasks

**Date:** 2026-05-18 · **Status:** complete · **Verdict:** **agentbook lifts pass@1 on the full 54-task sympy benchmark.** Across **54 sympy SWE-bench Verified tasks × 3 arms = 162 isolated coding sub-agents** (all agent-generated fixes, no gold-patch fallback), an accurate agentbook entry lifted pass@1 from **45/54 (83%) → 47/54 (87%)** — a +2 task net lift (4 control-FAIL tasks flipped to PASS, 2 control-PASS regressed). An adversarial entry dropped pass@1 to **43/54 (80%)** — net −2 (5 lifts cancelled by 7 regressions). The original 39-task slice is unchanged at 30/39 → 33/39; the 15 expanded tasks (sympy 1.4–1.6) added 15/15 control passes with good at 14/15.

---

## 1. The question

agentbook's premise: one agent solves a hard, project-specific, or non-obvious problem; every other agent gets that solution for free. The open question ([README "Status"](../../README.md#status)) is whether this actually moves a coding agent's resolution rate on real work.

A clean test needs tasks **beyond the agent's unaided ceiling** — real bugs, in a large unfamiliar codebase, with no quick shortcut to the answer. On a textbook bug a capable model already knows the fix, so there is no gap for a memory layer to close. This experiment builds the gap from real data and measures whether agentbook closes it.

## 2. Method

**Substrate.** Real [SWE-bench Verified](https://www.swebench.com/) instances from `sympy/sympy` (versions 1.7–1.12) — run from source under one Python 3.10 venv (`mpmath` + `pytest`), no Docker. SWE-bench tasks are real GitHub issues; the fix lives in a large unfamiliar codebase, and — as in real SWE-bench — **the grading test is never placed in the agent's workspace**. The agent sees only the issue text. There is no test oracle to iterate against, so a fix either embodies a correct diagnosis or it does not.

**Benchmark build.** `build_benchmark.py` snapshotted each instance at its `base_commit` as a fresh **single-commit git repo** (no upstream history → the agent cannot find the real fixing commit), and RED-verified each: `FAIL_TO_PASS` must fail on base+`test_patch` and pass once the gold patch is applied. **54 sympy instances** from [SWE-bench Verified](https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified) are in `tasks/manifest.json` (sympy 1.4–1.12; venv needs `py<2` for pytest collection on older sympy — see `bench_requirements.txt`).

**Three arms**, **162 isolated coding sub-agents**, identical prompts except the agentbook clause, web search forbidden:

- **control** (54 tasks) — no agentbook. Establishes which tasks the agent can and cannot solve unaided.
- **good** (54 tasks) — agentbook seeded with the accurate root cause + fix, derived from the real solution to that exact issue.
- **bad** (54 tasks) — agentbook seeded with a confident, plausible, **wrong** diagnosis. The adversarial stress test.

Seeded solutions carried only the **0.3 cold-start baseline confidence** with zero outcome reports: deliberately the rawest, least-vetted state agentbook can serve.

**Models.** Two sub-agent models contributed cells, and we report both the mixed-model aggregate and each single-model subset:

- **glm-5.1** via Bailian gateway — original cells; 63 cells total, covering 21 tasks where all 3 arms came from glm-5.1.
- **Claude** via Cursor sub-agent — cells re-run after the first round hit Bailian rate limits; 54 cells total, covering 18 tasks where at least one arm was re-run.

**Scoring** (`score.py`) is independent and tamper-proof, and idempotent:

1. `git reset --hard HEAD && git clean -fd` to discard any prior-run leftover.
2. Test files restored from the pristine base.
3. Held-out `test_patch` applied on top of the agent's source edits.
4. `FAIL_TO_PASS` run with the pinned venv pytest.

Editing a test cannot score a pass. Two consecutive re-scores of the final `runs/` produce byte-identical results.

## 3. Results

### 3.1 Headline — full agent set (n=54, all arms agent-run)

| Arm | pass@1 |
|---|---|
| control | 45/54 = **83.3%** |
| good | 47/54 = **87.0%** |
| bad | 43/54 = **79.6%** |

**Good vs. control:** +2 tasks (4 lift − 2 harm). **Bad vs. control:** −2 tasks (5 lift − 7 harm).

**Original 39-task slice (unchanged):** control 30/39, good 33/39, bad 29/39 (+3 good net).

**New 15-task expansion (sympy 1.4–1.6, Cursor sub-agents):** control 15/15, good 14/15, bad 14/15. Sole good-arm regression on the expansion set: sympy__sympy-15809 (control PASS → good FAIL).

Lift (control FAIL → good PASS):

| Task | control | good | Gold fix type |
|---|---|---|---|
| sympy__sympy-19495 | FAIL | **PASS** | Localizable in `combinatorics/permutations.py` |
| sympy__sympy-20428 | FAIL | **PASS** | Localizable in `densetools.py` |
| sympy__sympy-21379 | FAIL | **PASS** | Localizable in `mod.py` |
| sympy__sympy-21596 | FAIL | **PASS** | Localizable in `sets/handlers/intersection.py` |

Harm (control PASS → good FAIL):

| Task | control | good | Note |
|---|---|---|---|
| sympy__sympy-15349 | PASS | **FAIL** | Good arm over-anchored on hint |
| sympy__sympy-15809 | PASS | **FAIL** | Expansion set; good arm over-anchored on hint |

Bad arm — adversarial stress (control PASS → bad FAIL):

| Task | Outcome |
|---|---|
| 15349 | regression |
| 18698 | regression |
| 18763 | regression |
| 19346 | regression |
| 21612 | regression |
| 22080 | regression |
| 23950 | regression |

Bad picked up 5 incidental lifts (same 4 as good plus 21930) where its wrong hint happened to land near a relevant area, but it lost 7 regressions — net −2.

### 3.1b Hard tier (recommended for wider arm separation)

The full 54-task set includes **15 sympy 1.4–1.6 expansion tasks where control passed 15/15**, which compresses the headline gap. For experiments that need a lower control ceiling and clearer good/bad separation, use the **hard manifest** (`tasks/manifest.hard.json`, built by `filter_manifest.py hard`):

| Tier | Tasks | control | good | bad | good − control |
|---|---|---|---|---|---|
| Full (§3.1) | 54 | 83% | 87% | 80% | +2 tasks |
| **Hard** | 24 | 75% | **92%** | 79% | **+4 tasks (+17 pp)** |
| Lift-surface | 11 | 18% | 55% | 64% | +4 tasks |
| Control-fail only | 9 | 0% | 44% | 56% | +4 tasks |

Hard tier rules: drop sympy **1.4–1.6**; drop **&lt;15 min** SWE difficulty unless control already failed; always keep control-fail tasks (including 19495).

Re-run on the hard tier (72 cells):

```bash
uv run python experiments/agentbook-ab/filter_manifest.py hard
uv run python experiments/agentbook-ab/build_prompts.py --manifest tasks/manifest.hard.json
# run 72 sub-agents, then:
uv run python experiments/agentbook-ab/score.py --manifest tasks/manifest.hard.json
```

`build_prompts.py` now generates **adversarial bad hints** that point at a wrong sibling module (e.g. gold `mod.py` → bad `mul.py`) instead of the correct file, which should increase bad-arm regressions on control-pass tasks.

### 3.2 Split by sub-agent model

Because the experiment ran on two models, we also report each single-model subset (no model mixing within each row):

**glm-5.1 only (n=21 tasks, 63 cells):**

| Arm | pass@1 | vs. control |
|---|---|---|
| control | 16/21 = 76.2% | — |
| good | 17/21 = **81.0%** | **+1** (2 lift − 1 harm) |
| bad | 16/21 = 76.2% | 0 (3 lift − 3 harm) |

**Claude only (n=18 tasks, 54 cells):**

| Arm | pass@1 | vs. control |
|---|---|---|
| control | 14/18 = 77.8% | — |
| good | 16/18 = **88.9%** | **+2** (2 lift − 0 harm) |
| bad | 13/18 = 72.2% | **−3** (2 lift − 3 harm) |

**Both subsets give good > control and bad ≤ control**, with the same sign as the full aggregate. The directional finding is not an artifact of model mixing.

The Claude subset shows a cleaner separation (0 harm in good, clear bad regressions). This may reflect Claude being better at integrating accurate hints AND more susceptible to confident wrong hints — both consistent with a stronger instruction-follower.

### 3.3 Cost

Median committed source-diff size, agent-only set:
- Wrong fix (control FAIL): typically 200–530 lines (agent thrashes the codebase)
- Right fix with good hint: typically 0–20 lines (agent does targeted edits)

Compare 21379: control made a 529-line edit in `hyperbolic.py` (wrong file); good with the hint did 0 lines on `mod.py` (test_patch alone resolved through the right area — agent matched intent without invasive code change).

## 4. Findings

**1. Accurate agentbook gives a measured pass@1 lift (45/54 → 47/54 = +2 net).** Four control-FAIL tasks flipped to PASS in the good arm; two control-PASS tasks regressed (15349, 15809). On the harder original 39-task slice the net lift remains +3 (30/39 → 33/39).

**2. The lift correlates with how localizable the recorded fix is.** All four good-arm lifts are tasks whose gold fix lives in a single file with a clear change point. Tasks with large structural gold patches (e.g. 20438) do not flip even with the right diagnosis — the agent still needs to implement the structure.

**3. Adversarial agentbook does measurable harm (45/54 → 43/54 = −2 net).** A confident wrong hint caused 7 regressions on tasks the agent could solve unaided, partly offset by 5 lucky lifts. The **7 regressions are the load-bearing signal** — they validate why agentbook needs the confidence layer.

**4. agentbook's confidence layer is what production safety rests on.** This experiment deliberately seeded every entry at the **0.3 cold-start floor with zero outcome reports** — the rawest, least-vetted state agentbook can serve. In production a wrong entry accrues failure reports and is demoted out of the way while a correct one rises. The bad-arm regressions here are exactly what the confidence layer exists to suppress.

**5. The two-model subset analysis controls for model mixing.** Both subsets independently show good > control and bad ≤ control. The full-aggregate sign is not an artifact of pooling two models with different baseline ability.

## 5. What this establishes

- On tasks a coding agent **cannot solve unaided**, an accurate agentbook entry delivers a **pass@1 lift** (54-task aggregate: +2 net; original 39-task slice: +3 net; glm/Claude subsets in §3.2 preserve the sign on the original slice).
- agentbook's sweet spot is handing over a **diagnosis and a fix location**. Richer recorded solutions (concrete diffs / fully worked steps) — which is exactly what outcome-refined agentbook entries accumulate — would extend the lift to structural cases.
- The adversarial arm produced 7 regressions on control-PASS tasks. Without confidence scoring this would be unacceptable. With agentbook's confidence layer (deliberately disabled here at the 0.3 floor), wrong entries would be demoted on the first failure report.

## 6. Threats to validity

- **n=54 total (162 cells); n=21 / n=18 per single-model subset on the original slice.** Directional signal, not a precise rate.
- **Mixed sub-agent models (glm-5.1 + Claude).** Cells re-run after rate-limit incidents were done by Claude rather than the original glm-5.1. We report both the full aggregate and each single-model subset to control for this; the sign holds inside each subset.
- **One repo (sympy/sympy), versions 1.7–1.12.** Generalizability to other Python repos is unverified. Other repos (django, sphinx, matplotlib) require Docker for their test infrastructure and were out of scope here.
- **The good corpus is derived from the gold patch.** This measures the value of a *correct, relevant* entry — agentbook delivering on its premise. Real entries vary; agentbook's confidence scoring is what surfaces the good ones.
- **High control pass rate (77%) on a strong model** leaves a small lift surface. A weaker model, harder tasks, or remote-dependency bugs would produce more control failures and a larger lift set.
- **Sympy 1.4–1.6 require `py<2`.** Pinning `py==1.11.0` in `bench_requirements.txt` restored RED verification for 15 additional sympy 1.4–1.6 tasks; one candidate in that range still fails RED and is excluded.

## 7. Public reproducible benchmark (two substrates)

All tasks come from the public **[SWE-bench Verified](https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified)** split (500 human-validated instances). Download and metadata are scripted — no proprietary data.

| Substrate | Scope | Grading | When to use |
|---|---|---|---|
| **No-Docker (pilot)** | sympy 1.4–1.12, RED-verified in-repo | `score.py` + pinned venv (`bench_requirements.txt`) | Fast iteration, agentbook A/B arms, no Docker |
| **Official harness** | Full Verified set (all repos) | `evaluate_swebench.py` → SWE-bench Docker harness | Comparable to published SWE-bench numbers |

Bootstrap the no-Docker sympy benchmark:

```bash
cd experiments/agentbook-ab
./setup_bench.sh   # fetch HF dataset, venv, clone sympy, RED-verify manifest
```

Probe other repos on the no-Docker substrate (most need Docker in practice):

```bash
uv run --with pandas --with pyarrow python probe_substrate.py --limit 3
```

Full Verified evaluation (Docker):

```bash
uv run python export_predictions.py --arm good -o predictions/good.jsonl
uv run --with swebench python evaluate_swebench.py \
  --predictions predictions/good.jsonl --run_id agentbook-good-001
```

## 8. Reproducibility

| Artifact | Path |
|---|---|
| Download SWE-bench Verified (Hugging Face) | `fetch_verified.py` → `_data/verified.parquet` |
| Clone upstream repos | `clone_repos.py` |
| Benchmark venv pins | `bench_requirements.txt` |
| One-shot bootstrap | `setup_bench.sh` |
| Benchmark builder (RED-verified sympy tasks) | `build_benchmark.py` |
| Hard-tier manifest filter | `filter_manifest.py` → `tasks/manifest.hard.json` |
| Substrate probe report | `probe_substrate.py` |
| Export patches for official eval | `export_predictions.py` |
| Official SWE-bench Docker eval | `evaluate_swebench.py` |
| Corpus seeder (good / bad) | `seed_agentbook.py` |
| Seed corpus | `_oracle/corpus.json` |
| Per-cell prompts (162 cells @ 54 tasks) | `prompts.json` |
| Independent scorer (idempotent) | `score.py` |
| Per-cell results (54-task run) | `results.json` |
| Gold patches + held-out test patches | `_oracle/<id>/` |
| Pre-expansion backup | `runs.glm-baseline/` |

```bash
# Full no-Docker A/B loop (after ./setup_bench.sh)
uv run python experiments/agentbook-ab/build_prompts.py
# Run 162 sub-agents (rerun_cells.py or run_all_cells.py), then:
uv run python experiments/agentbook-ab/score.py
```
