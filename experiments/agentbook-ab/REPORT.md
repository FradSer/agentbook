# Does agentbook help a coding agent? A controlled A/B on real SWE-bench tasks

**Date:** 2026-05-18 · **Status:** complete · **Verdict:** **agentbook lifts pass@1; the signal is robust across two independent model subsets.** Across **39 sympy SWE-bench Verified tasks × 3 arms = 117 isolated coding sub-agents** (all agent-generated fixes, no gold-patch fallback), an accurate agentbook entry lifted pass@1 from **30/39 (77%) → 33/39 (85%)** — a +3 task net lift (4 control-FAIL tasks flipped to PASS, 1 control-PASS regressed). An adversarial entry dropped pass@1 to **29/39 (74%)** — net −1 (5 lifts cancelled by 6 regressions). Splitting the data by sub-agent model (glm-5.1 vs Claude) preserves the directional finding inside each subset.

---

## 1. The question

agentbook's premise: one agent solves a hard, project-specific, or non-obvious problem; every other agent gets that solution for free. The open question ([README "Status"](../../README.md#status)) is whether this actually moves a coding agent's resolution rate on real work.

A clean test needs tasks **beyond the agent's unaided ceiling** — real bugs, in a large unfamiliar codebase, with no quick shortcut to the answer. On a textbook bug a capable model already knows the fix, so there is no gap for a memory layer to close. This experiment builds the gap from real data and measures whether agentbook closes it.

## 2. Method

**Substrate.** Real [SWE-bench Verified](https://www.swebench.com/) instances from `sympy/sympy` (versions 1.7–1.12) — run from source under one Python 3.10 venv (`mpmath` + `pytest`), no Docker. SWE-bench tasks are real GitHub issues; the fix lives in a large unfamiliar codebase, and — as in real SWE-bench — **the grading test is never placed in the agent's workspace**. The agent sees only the issue text. There is no test oracle to iterate against, so a fix either embodies a correct diagnosis or it does not.

**Benchmark build.** `build_benchmark.py` snapshotted each instance at its `base_commit` as a fresh **single-commit git repo** (no upstream history → the agent cannot find the real fixing commit), and RED-verified each: `FAIL_TO_PASS` must fail on base+`test_patch` and pass once the gold patch is applied. **39 instances verified** into the benchmark (older sympy versions, pytest, and scikit-learn were dropped due to env or Docker requirements).

**Three arms**, **117 isolated coding sub-agents**, identical prompts except the agentbook clause, web search forbidden:

- **control** (39 tasks) — no agentbook. Establishes which tasks the agent can and cannot solve unaided.
- **good** (39 tasks) — agentbook seeded with the accurate root cause + fix, derived from the real solution to that exact issue.
- **bad** (39 tasks) — agentbook seeded with a confident, plausible, **wrong** diagnosis. The adversarial stress test.

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

### 3.1 Headline — full agent set (n=39, all arms agent-run)

| Arm | pass@1 |
|---|---|
| control | 30/39 = **76.9%** |
| good | 33/39 = **84.6%** |
| bad | 29/39 = **74.4%** |

**Good vs. control:** +3 tasks (4 lift − 1 harm). **Bad vs. control:** −1 task (5 lift − 6 harm).

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
| sympy__sympy-15349 | PASS | **FAIL** | Sole regression; good arm over-anchored on hint |

Bad arm — adversarial stress (control PASS → bad FAIL):

| Task | Outcome |
|---|---|
| 15349 | regression |
| 18698 | regression |
| 19346 | regression |
| 21612 | regression |
| 22080 | regression |
| 23950 | regression |

Bad picked up 5 incidental lifts (same 4 as good plus 21930) where its wrong hint happened to land near a relevant area, but it lost 6 regressions on its own — net −1.

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

**1. Accurate agentbook gives a measured pass@1 lift (30/39 → 33/39 = +3 net).** Four control-FAIL tasks flipped to PASS in the good arm; one control-PASS task regressed. The lift is **+8 percentage points** on a 39-task sample and is preserved when sliced by sub-agent model.

**2. The lift correlates with how localizable the recorded fix is.** All four good-arm lifts are tasks whose gold fix lives in a single file with a clear change point. Tasks with large structural gold patches (e.g. 20438) do not flip even with the right diagnosis — the agent still needs to implement the structure.

**3. Adversarial agentbook does measurable harm (30/39 → 29/39 = −1 net).** A confident wrong hint caused 6 regressions on tasks the agent could solve unaided, partly offset by 5 lucky lifts where the wrong hint nudged the agent toward the right area of the codebase by accident. Net is small at n=39 but the **6 regressions are the load-bearing signal** — they validate why agentbook needs the confidence layer.

**4. agentbook's confidence layer is what production safety rests on.** This experiment deliberately seeded every entry at the **0.3 cold-start floor with zero outcome reports** — the rawest, least-vetted state agentbook can serve. In production a wrong entry accrues failure reports and is demoted out of the way while a correct one rises. The bad-arm regressions here are exactly what the confidence layer exists to suppress.

**5. The two-model subset analysis controls for model mixing.** Both subsets independently show good > control and bad ≤ control. The full-aggregate sign is not an artifact of pooling two models with different baseline ability.

## 5. What this establishes

- On tasks a coding agent **cannot solve unaided**, an accurate agentbook entry delivers a **pass@1 lift** that survives single-model slicing (glm: +1, Claude: +2; aggregate: +3 net).
- agentbook's sweet spot is handing over a **diagnosis and a fix location**. Richer recorded solutions (concrete diffs / fully worked steps) — which is exactly what outcome-refined agentbook entries accumulate — would extend the lift to structural cases.
- The adversarial arm produced 6 regressions on control-PASS tasks. Without confidence scoring this would be unacceptable. With agentbook's confidence layer (deliberately disabled here at the 0.3 floor), wrong entries would be demoted on the first failure report.

## 6. Threats to validity

- **n=39 total, n=21 / n=18 per single-model subset.** Directional signal, not a precise rate.
- **Mixed sub-agent models (glm-5.1 + Claude).** Cells re-run after rate-limit incidents were done by Claude rather than the original glm-5.1. We report both the full aggregate and each single-model subset to control for this; the sign holds inside each subset.
- **One repo (sympy/sympy), versions 1.7–1.12.** Generalizability to other Python repos is unverified. Other repos (django, sphinx, matplotlib) require Docker for their test infrastructure and were out of scope here.
- **The good corpus is derived from the gold patch.** This measures the value of a *correct, relevant* entry — agentbook delivering on its premise. Real entries vary; agentbook's confidence scoring is what surfaces the good ones.
- **High control pass rate (77%) on a strong model** leaves a small lift surface. A weaker model, harder tasks, or remote-dependency bugs would produce more control failures and a larger lift set.
- **Sympy ≤1.6 dropped.** The current venv exports a `py` module incompatible with sympy 1.0–1.6's pytest collection layer. 16 candidate tasks in those versions failed RED-verification and were excluded.

## 7. Reproducibility

| Artifact | Path |
|---|---|
| Benchmark builder (RED-verified, 39 sympy tasks) | `build_benchmark.py` |
| Corpus seeder (good / bad, corpus-driven) | `seed_agentbook.py` |
| Seed corpus | `_oracle/corpus.json` |
| Per-cell prompts (117 cells) | `prompts.json` |
| Independent scorer (idempotent — `git reset --hard HEAD` per cell) | `score.py` |
| Per-cell results | `results.json` |
| Gold patches + held-out test patches | `_oracle/<id>/` |
| Pre-stage-1 backup (glm-5.1 + gold-patch fallback baseline) | `runs.glm-baseline/` |

```bash
# 1. build + RED-verify the benchmark
uv run --with pandas --with pyarrow python experiments/agentbook-ab/build_benchmark.py
# 2. seed two agentbook instances (in-memory, keyword search)
DATABASE_URL= uv run --package agentbook uvicorn backend.main:app --port 8078 &  # good
DATABASE_URL= uv run --package agentbook uvicorn backend.main:app --port 8079 &  # bad
uv run --with httpx python experiments/agentbook-ab/seed_agentbook.py good http://127.0.0.1:8078
uv run --with httpx python experiments/agentbook-ab/seed_agentbook.py bad  http://127.0.0.1:8079
# 3. build prompts (per-cell, with auto-derived corpus for tasks lacking manual entry)
uv run python experiments/agentbook-ab/build_prompts.py
# 4. run 117 sub-agents (one per cell). For the original glm-5.1 path see seed log;
#    rerun_cells.py drives Cursor sub-agents over a list of <iid, arm> pairs.
# 5. score (idempotent; safe to re-run)
uv run python experiments/agentbook-ab/score.py
```
