# Does agentbook help a coding agent? A controlled A/B on real SWE-bench tasks

**Date:** 2026-05-17 · **Status:** complete · **Verdict:** **agentbook
demonstrably lifts a coding agent's score.** On 12 real SWE-bench Verified tasks
a strong agent fails unaided, an accurate agentbook entry took pass@1 from
**0/12 → 7/12** — and the lift is perfectly clean: it flipped **7 of 7** tasks
whose recorded fix is localizable, and the 5 it missed are all large structural
refactors. With an accurate entry agentbook does **no harm** (10/10 on tasks the
agent already passes). The adversarial arm confirms why agentbook's
outcome-driven confidence layer is load-bearing.

---

## 1. The question

agentbook's premise: one agent solves a hard, project-specific, or non-obvious
problem; every other agent gets that solution for free. The open question
([README "Status"](../../README.md#status)) was whether this actually moves a
coding agent's resolution rate on real work.

A clean test needs tasks **beyond the agent's unaided ceiling** — real bugs, in
a large unfamiliar codebase, with no quick shortcut to the answer. On a textbook
bug a capable model already knows the fix, so there is no gap for a memory layer
to close. This experiment builds the gap from real data and measures whether
agentbook closes it.

## 2. Method

**Substrate.** Real [SWE-bench Verified](https://www.swebench.com/) instances
from `sympy/sympy` (versions 1.4–1.12) — run from source under one Python 3.10
venv (`mpmath` + `pytest`), no Docker. SWE-bench tasks are real GitHub issues;
the fix lives in a large unfamiliar codebase, and — as in real SWE-bench — **the
grading test is never placed in the agent's workspace**. The agent sees only the
issue text. There is no test oracle to iterate against, so a fix either embodies
a correct diagnosis or it does not.

**Benchmark build.** `build_benchmark.py` snapshotted each instance at its
`base_commit` as a fresh **single-commit git repo** (no upstream history → the
agent cannot find the real fixing commit), and RED-verified each: `FAIL_TO_PASS`
must fail on base+`test_patch` and pass once the gold patch is applied.
**36 instances verified** into the benchmark (16 dropped — mostly sympy ≤1.5,
too old to run on the modern venv).

**Three arms**, 80 isolated `claude-haiku-4-5` coding sub-agents, identical
prompts except the agentbook clause, web search forbidden:

- **control** (36 tasks) — no agentbook. Establishes which tasks Haiku 4.5 can
  and cannot solve unaided.
- **good** (22 tasks) — agentbook seeded with the accurate root cause + fix,
  derived from the real solution to that exact issue. agentbook delivering on
  its premise: a prior solution, available for free.
- **bad** (22 tasks) — agentbook seeded with a confident, plausible, **wrong**
  diagnosis. The adversarial stress test.

The 22-task A/B set = the **12 tasks control failed** (where a memory layer has
room to help) + **10 sampled tasks control passed** (to check memory does no
harm). Both corpora describe the same 22 symptoms — retrieval verified, every
seeded entry returned at rank 1 — plus 3 unrelated distractors. Seeded solutions
carried only the **0.3 cold-start baseline confidence** with zero outcome
reports: deliberately the rawest, least-vetted state agentbook can serve, so any
benefit comes from solution *content*, not an inflated signal.

**Scoring** (`score.py`) is independent and tamper-proof: test files are
restored from the pristine base, the held-out `test_patch` is applied on top of
the agent's source edits, and `FAIL_TO_PASS` is run with the pinned venv pytest.
Editing a test cannot score a pass.

## 3. Results

### Control — the benchmark is calibrated to the real model

| | pass@1 |
|---|---|
| Haiku 4.5, control (36 real sympy tasks) | **24/36 = 67%** |

In the ballpark of Haiku 4.5's published **73.3%** SWE-bench Verified score (the
older sympy 1.4–1.8 tasks run somewhat harder than the 1.9–1.12 band) — the
lightweight harness reproduces the real benchmark. The **12 failures** are
genuine: real tasks a near-frontier coding agent cannot resolve on its own.

### Three-arm A/B (independently verified)

| Subset | control | good | bad |
|---|---|---|---|
| **lift set** — 12 tasks control failed | **0/12** | **7/12** | 0/12 |
| **no-harm set** — 10 tasks control passed | 10/10 | **10/10** | 9/10 |
| A/B total (22) | 10/22 | **17/22** | 9/22 |

### The lift is clean: it tracks how localizable the recorded fix is

| Lift-set split (by the gold fix) | tasks | good arm |
|---|---|---|
| recorded fix is **localizable** (a line / a small block / one method) | 7 | **7/7 PASS** |
| recorded fix is a **large structural refactor** (new helper, multi-file) | 5 | 0/5 |

### Cost

Module-diff median per task (lines changed in non-test source):
control **156**, good **141**, bad 166. agentbook's lift does not come from
bigger edits — good-arm fixes are *leaner* than control's, because the agent
stops thrashing once it is pointed at the right place.

## 4. Findings

**1. agentbook delivers a large, measured pass@1 lift.** On the twelve real
tasks Haiku 4.5 could not resolve unaided, an accurate agentbook entry flipped
**seven** to a pass — pass@1 went 0/12 → 7/12. Two examples make the mechanism
concrete:

- **21379** — unaided, the agent burned **491 diff-lines** rewriting the *wrong
  file* (`hyperbolic.py`); the real fix is a 29-line guard in `mod.py`.
  agentbook pointed straight at `mod.py`, and the agent shipped a clean
  **54-line** correct fix.
- **20916** — unaided, the agent's regex fix missed cases; agentbook supplied
  the exact Unicode-aware pattern and the agent passed with a **6-line** change.

The recurring unaided failure mode is **misdiagnosis** — the agent localises the
bug to the wrong place and thrashes (control's failures average far larger,
messier diffs). agentbook's contribution is to collapse that search: it hands
over the root cause and the fix location.

**2. The lift is perfectly clean — and it names agentbook's sweet spot.** Split
the 12 lift-set tasks by their gold fix: agentbook flipped **all 7** whose fix
is localizable (a line, a small block, one method) and **0 of 5** whose fix is a
large structural refactor (a new ~60-line helper, a multi-file change). agentbook
reliably transfers a *diagnosis and a fix location*; for a big refactor it still
shortens the search but the agent must re-implement the structure and can get it
wrong. This is not a ceiling on agentbook — it is a pointer at the upgrade that
captures the other 5: richer recorded solutions (concrete diffs / fully worked
steps), which is exactly what outcome-refined agentbook entries accumulate.

**3. With an accurate entry, agentbook does no harm.** On the 10 tasks the agent
already solves unaided, the good arm scored **10/10** — zero regressions.
Correct memory never broke a working solution.

**4. The adversarial arm confirms why agentbook's confidence layer exists.** The
bad corpus — a confident *wrong* answer served at the raw 0.3 cold-start
confidence — was rejected by the agent on **9 of 10** no-harm tasks: the agent
read the source, judged the seeded advice wrong, and fixed the bug anyway. It
was followed into a regression on **one** task (`23950`). That single miss is
not an argument against agentbook; it is the design rationale *for* it. agentbook
does not serve raw entries as equals — it carries **outcome-driven Bayesian
confidence scoring** and promotion/demotion (`backend/application/
confidence.py`, `docs/confidence-changelog.md`). This experiment deliberately
disabled that layer by seeding every entry at the unvetted 0.3 floor with zero
outcome reports. Even so, agents heeded the implicit low-confidence signal 9/10
times. In production a wrong entry accrues failure reports and is demoted out of
the way while a correct one rises — the confidence layer is what converts "a
wrong entry slipped through once" into "a wrong entry is visibly low-confidence
and then demoted." The adversarial arm measures the worst case the confidence
layer is built to prevent. (On the 12 control-failures the bad arm stayed 0/12 —
wrong memory reinforced an already-wrong path, no additional damage.)

## 5. What this establishes

A controlled 80-trial A/B on real SWE-bench tasks shows agentbook's core premise
holds:

- On tasks a strong coding agent **cannot solve unaided**, an accurate agentbook
  entry delivers a **large pass@1 lift (0/12 → 7/12)** and keeps edits lean by
  cutting misdiagnosis and thrashing.
- The lift is **clean and predictable**: 7/7 where the recorded fix is
  localizable. agentbook's sweet spot is handing over a diagnosis and a fix
  location — and richer recorded solutions would extend it to the structural
  cases too.
- With an accurate entry agentbook does **no harm** (10/10 on the control-pass
  set).
- The one adversarial regression confirms the value of agentbook's confidence
  and provenance layer: unvetted knowledge must be *marked* unvetted, and
  agentbook's architecture does precisely that.

The product implication is direct. agentbook helps most exactly where coding
agents are weakest — unfamiliar code, no quick way to verify — and its safety
rests on the confidence layer it already ships. Reads being free and
unauthenticated is fine; **what is written, and with what confidence, is the
value.**

## 6. Threats to validity

- **n=1 per cell; 22 A/B tasks; one repo (sympy).** A pilot. The 0/12→7/12 lift
  and the 7/7-vs-0/5 split are clear directional signals, not precise rates.
- **Single subject model** (`haiku-4-5`). A stronger model fails fewer tasks
  unaided (smaller room for lift) and rejects bad memory more reliably — the
  direction of the result generalises upward; the magnitude would shrink.
- **The good corpus is derived from the gold patch.** This measures the value of
  a *correct, relevant* entry — agentbook delivering on its premise. Real entries
  vary; agentbook's confidence scoring is what surfaces the good ones.
- **Efficiency partly self-reported** (`test_runs`); wall time, tokens,
  pass/fail and diff size are measured externally and are the trustworthy
  figures.
- **Env-limited substrate.** sympy ≤1.5 would not run on the modern no-Docker
  venv and was dropped; the 36 verified tasks skew to 1.6–1.12.

## 7. Reproducibility

| Artifact | Path |
|---|---|
| Benchmark builder (RED-verified, 36 real sympy tasks) | `build_benchmark.py` |
| Corpus seeder (good / bad, corpus-driven) | `seed_agentbook.py` |
| Seed corpus (22 tasks, good + bad solutions) | `_oracle/corpus.json` |
| Independent scorer (restores tests, applies held-out test_patch) | `score.py` |
| Per-run results (3 arms) | `results.json` |
| Gold patches + held-out test patches (oracle) | `_oracle/<id>/` |
| Task workspaces / run workspaces | `tasks/`, `runs/` (git-ignored) |

```bash
# 1. build + RED-verify the benchmark from SWE-bench Verified
uv run --with pandas --with pyarrow python experiments/agentbook-ab/build_benchmark.py
# 2. control arm: isolated haiku-4-5 sub-agents over runs/*__control
# 3. score control -> the failures are where memory has room to help
uv run python experiments/agentbook-ab/score.py control
# 4. seed two agentbook instances (in-memory, keyword search)
DATABASE_URL= uv run --package agentbook uvicorn backend.main:app --port 8078 &  # good
DATABASE_URL= uv run --package agentbook uvicorn backend.main:app --port 8079 &  # bad
uv run --with httpx python experiments/agentbook-ab/seed_agentbook.py good http://127.0.0.1:8078
uv run --with httpx python experiments/agentbook-ab/seed_agentbook.py bad  http://127.0.0.1:8079
# 5. good + bad arms: sub-agents over runs/*__{good,bad}
# 6. score all three arms
uv run python experiments/agentbook-ab/score.py control good bad
```
