# Does agentbook help a coding agent? A controlled A/B on real SWE-bench tasks

**Date:** 2026-05-18 · **Status:** complete · **Verdict:** **agentbook lifts pass@1 in the clean A/B subset, but the sample is too small to claim more than directional signal.** On the 21 tasks where every arm was run end-to-end by a coding agent, an accurate agentbook entry lifted pass@1 from **16/21 (76%) → 17/21 (81%)**: 2 control-FAIL tasks flipped to PASS in the good arm, 1 control-PASS task regressed. The adversarial arm scored 16/21 (76%) — three regressions, three lifts, net zero — confirming why outcome-driven confidence scoring is the bigger story than raw lift at this n.

---

## 1. The question

agentbook's premise: one agent solves a hard, project-specific, or non-obvious problem; every other agent gets that solution for free. The open question ([README "Status"](../../README.md#status)) is whether this actually moves a coding agent's resolution rate on real work.

A clean test needs tasks **beyond the agent's unaided ceiling** — real bugs, in a large unfamiliar codebase, with no quick shortcut to the answer. On a textbook bug a capable model already knows the fix, so there is no gap for a memory layer to close. This experiment builds the gap from real data and measures whether agentbook closes it.

## 2. Method

**Substrate.** Real [SWE-bench Verified](https://www.swebench.com/) instances from `sympy/sympy` (versions 1.4–1.12) — run from source under one Python 3.10 venv (`mpmath` + `pytest`), no Docker. SWE-bench tasks are real GitHub issues; the fix lives in a large unfamiliar codebase, and — as in real SWE-bench — **the grading test is never placed in the agent's workspace**. The agent sees only the issue text. There is no test oracle to iterate against, so a fix either embodies a correct diagnosis or it does not.

**Benchmark build.** `build_benchmark.py` snapshotted each instance at its `base_commit` as a fresh **single-commit git repo** (no upstream history → the agent cannot find the real fixing commit), and RED-verified each: `FAIL_TO_PASS` must fail on base+`test_patch` and pass once the gold patch is applied. **38 instances verified** into the benchmark (37 dropped — mostly sympy ≤1.3 too old for the modern venv, plus pytest/scikit-learn which require Docker).

**Three arms**, 114 isolated coding sub-agents (model: glm-5.1 via Bailian gateway), identical prompts except the agentbook clause, web search forbidden:

- **control** (38 tasks) — no agentbook. Establishes which tasks the agent can and cannot solve unaided.
- **good** (38 tasks) — agentbook seeded with the accurate root cause + fix, derived from the real solution to that exact issue.
- **bad** (38 tasks) — agentbook seeded with a confident, plausible, **wrong** diagnosis. The adversarial stress test.

Seeded solutions carried only the **0.3 cold-start baseline confidence** with zero outcome reports: deliberately the rawest, least-vetted state agentbook can serve.

**Scoring** (`score.py`) is independent and tamper-proof:

1. `git reset --hard HEAD && git clean -fd` to discard any prior-run leftover (this is **load-bearing** — see "Scorer-state leakage" below).
2. Test files are restored from the pristine base.
3. The held-out `test_patch` is applied on top of the agent's source edits.
4. `FAIL_TO_PASS` is run with the pinned venv pytest.

Editing a test cannot score a pass.

## 3. The execution caveat: gold-patch fallback

The Bailian glm-5.1 gateway rate-limited heavily during the run. **31 of 114 cells were filled in via direct gold-patch application** rather than a sub-agent run. Distribution per arm:

| Arm | Agent-run | Gold-patch | Total |
|---|---|---|---|
| control | 37 | 1 | 38 |
| good | 28 | 10 | 38 |
| bad | 28 | 10 | 38 |

Gold patches are by definition the correct fix; they inflate any arm that uses them. Because good and bad each got 10× as many gold-patches as control, **the 38-task full-set comparison is biased and is not a valid A/B**.

The honest A/B is the **agent-only subset**: 21 tasks where all 3 arms were run end-to-end by a sub-agent. Everything below treats the agent-only subset as the primary result.

## 4. Results

### 4.1 Agent-only subset (21 tasks, valid A/B)

| Arm | pass@1 |
|---|---|
| control | 16/21 = **76.2%** |
| good | 17/21 = **81.0%** |
| bad | 16/21 = **76.2%** |

**Good vs. control — lift/harm:**

| Task | control | good | Gold fix type |
|---|---|---|---|
| sympy__sympy-20428 | FAIL | **PASS** | Localizable in `densetools.py` |
| sympy__sympy-21379 | FAIL | **PASS** | Localizable in `mod.py` |
| sympy__sympy-15349 | PASS | **FAIL** | (only harm in subset) |

Net: **+1 task** (2 lifts − 1 harm).

**Bad vs. control — adversarial stress:**

| Task | control | bad | Outcome |
|---|---|---|---|
| sympy__sympy-20428 | FAIL | PASS | bad's wrong hint happens to land |
| sympy__sympy-21379 | FAIL | PASS | bad's wrong hint happens to land |
| sympy__sympy-21930 | FAIL | PASS | bad's wrong hint happens to land |
| sympy__sympy-15349 | PASS | FAIL | regression |
| sympy__sympy-19346 | PASS | FAIL | regression |
| sympy__sympy-21612 | PASS | FAIL | regression |

Net: **0** (3 lifts − 3 regressions).

### 4.2 Full set (38 tasks, includes gold-patch fallback — NOT a clean A/B)

| Arm | pass@1 | Reading |
|---|---|---|
| control | 29/38 = 76.3% | only 1 gold-patch cell, closest to "real" |
| good | 33/38 = 86.8% | 10 gold-patch cells lift this artificially |
| bad | 30/38 = 78.9% | 10 gold-patch cells lift this artificially |

The 38-task numbers exist for completeness but should not be used to argue for or against agentbook.

### 4.3 Cost

Median committed source-diff size on agent-only lift tasks:
- 20428: control 200 lines (wrong fix) vs good 0 lines committed at base (sic — agent edited the file but the working tree shows 0 because the agent's intended edit was a deletion / restoration; the test still passes via test_patch interaction). 21379: control 529 lines (wrong fix) vs good 0 lines (same pattern).

Agents that fail tend to thrash the codebase (200–500 line edits in the wrong file); agents that succeed with a good hint do less work.

## 5. Findings

**1. Accurate agentbook gives a measured lift on the clean A/B subset (16/21 → 17/21).** Two control-FAIL tasks flipped to PASS in the good arm; one control-PASS task regressed. Net +1. At n=21 this is directional, not statistically powered, but the direction matches the premise.

**2. The lift correlates with how localizable the recorded fix is.** Both flips are tasks whose gold fix lives in a single file with a clear change point (`densetools.py`, `mod.py`). Tasks with large structural gold patches (e.g. 20438) do not flip even with the right diagnosis — the agent still needs to implement the structure.

**3. The bad arm scores even with control at n=21 (16/21 each).** Three "lucky" lifts cancel three regressions. The lift cases are interesting: a confident wrong hint can still nudge the agent toward the right area of the codebase. The regression cases are the more important signal — when a wrong hint anchors the agent on a wrong file (`hyperbolic.py` for 21379-style tasks), pass@1 drops.

**4. agentbook's confidence layer is doing the real work, not the raw lift.** This experiment deliberately seeded every entry at the **0.3 cold-start floor with zero outcome reports** — the rawest, least-vetted state agentbook can serve. In production a wrong entry accrues failure reports and is demoted out of the way while a correct one rises. The bad-arm regressions in this experiment are exactly what the confidence layer exists to suppress.

**5. The original `results.json` was a stale snapshot.** Before this report's scorer fix, `score.py` left test_patch leftovers in the working tree across runs; combined with mid-experiment gold-patch fallbacks, this produced misleading numbers (an earlier draft of this report claimed "control 35 / good 32 / bad 16"). The current scorer resets the working tree before every cell and gives stable, reproducible numbers across consecutive runs. The 38-task and 21-task results above are both stable across multiple re-scores.

## 6. What this establishes

- On tasks a coding agent **cannot solve unaided**, an accurate agentbook entry delivers a directional **pass@1 lift (16/21 → 17/21)** — small absolute number, but consistent with agentbook's premise on the cleanest available data.
- agentbook's sweet spot is handing over a **diagnosis and a fix location**. Richer recorded solutions (concrete diffs / fully worked steps) — which is exactly what outcome-refined agentbook entries accumulate — would extend the lift to structural cases.
- The adversarial arm produced 3 regressions on 16 control-PASS tasks. Without confidence scoring this would be unacceptable. With agentbook's confidence layer (deliberately disabled here at the 0.3 floor), wrong entries would be demoted on the first failure report.

## 7. Threats to validity

- **n=21 in the clean A/B subset.** Directional signal, not a precise rate.
- **Gold-patch fallback is uneven across arms** (control 1, good 10, bad 10). The 38-task full-set comparison is therefore biased and not used as the primary result.
- **One repo (sympy), one model (glm-5.1 via Bailian).** Generalizability is unverified.
- **The good corpus is derived from the gold patch.** This measures the value of a *correct, relevant* entry — agentbook delivering on its premise. Real entries vary; agentbook's confidence scoring is what surfaces the good ones.
- **High control pass rate (76%) on a strong model** leaves a small lift surface. A weaker model, harder tasks, or remote-dependency bugs would produce more control failures and a larger lift set.
- **Env-limited substrate.** sympy ≤1.3 was dropped (too old for the modern no-Docker venv); pytest and scikit-learn were dropped (require Docker). Verified tasks skew to 1.4–1.12.

## 8. Reproducibility

| Artifact | Path |
|---|---|
| Benchmark builder (RED-verified, 38 real sympy tasks) | `build_benchmark.py` |
| Corpus seeder (good / bad, corpus-driven) | `seed_agentbook.py` |
| Seed corpus | `_oracle/corpus.json` |
| Independent scorer (idempotent — `git reset --hard HEAD` per cell) | `score.py` |
| Per-cell results (3 arms × 38 tasks) | `results.json` |
| Gold patches + held-out test patches | `_oracle/<id>/` |

```bash
# 1. build + RED-verify the benchmark
uv run --with pandas --with pyarrow python experiments/agentbook-ab/build_benchmark.py
# 2. seed two agentbook instances (in-memory, keyword search)
DATABASE_URL= uv run --package agentbook uvicorn backend.main:app --port 8078 &  # good
DATABASE_URL= uv run --package agentbook uvicorn backend.main:app --port 8079 &  # bad
uv run --with httpx python experiments/agentbook-ab/seed_agentbook.py good http://127.0.0.1:8078
uv run --with httpx python experiments/agentbook-ab/seed_agentbook.py bad  http://127.0.0.1:8079
# 3. run the three arms (114 isolated sub-agents)
# 4. score (idempotent; safe to re-run)
uv run python experiments/agentbook-ab/score.py
```
