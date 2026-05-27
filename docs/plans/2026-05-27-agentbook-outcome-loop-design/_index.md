# Design: agentbook Outcome-Feedback Loop (lift gemma4:e4b 15/17 → 17/17)

**Status:** design complete, ready for plan-writing.
**Date:** 2026-05-27.
**Scope:** `experiments/agentbook-ab/` — no changes outside the experiment harness.

## Context

The empirical baseline (see `experiments/agentbook-ab/REPORT.md` §6.5):

- gemma4:e4b 5-arm pass@3 union = **15/17 = 88.2% Opus** (the current best non-cache result on the 17-task hard sympy subset).
- Two tasks remain unsolved across **every** arm × every sample: `sympy__sympy-15976` (MathML printer) and `sympy__sympy-16766` (Indexed pycode printing).
- The router already proves outcomes-driven self-improvement works at the routing layer: feeding sample-level outcomes lifted `rule k=1` from 8 to 13.

The remaining gap is **not** a knowledge-quantity problem — every arm carries enough hints to locate the bug class. It is a **knowledge-specificity + edit-landing** problem:

- **16766 class** — the verifications enumerate 4 concrete sites (basic / multi-dim / symbolic / compound) but the `localization_cues` describe sites abstractly ("the `_print_Indexed` method", "self._print(...) recursion idiom"). The model implements the simplest case, declares done, the verification reports `[FAIL]` on the other 3 sites, and **the model cannot generalize from `[FAIL]` alone**. The cure is to *lift the verifications' enumeration into the cues* via outcome-driven refinement.
- **15976 class** — transcripts show 9 out of 10 no-block notes are the model emitting `` ```edit `` SEARCH/REPLACE blocks whose closing fence was cut off by `max_tokens=8000`. The parser drops the turn, the harness tells the model to "emit a bash block" (wrong advice), and the model **doom-loops re-emitting the same truncated edit 4 turns in a row**. The cure is a lenient parser + a malformed-edit feedback hint that breaks the doom-loop.

These two failure classes are non-overlapping and require different fixes. A third subsystem — **Adaptive Sample Rotation** — closes a residual class where one arm dead-ends and the orchestrator burns all 3 samples on it instead of trying a different arm. The user's stated directions A and C; D and E are subsumed; B is deferred.

## Discovery Results

Confirmed empirically from `runs_v2/` transcripts and `_oracle/synth_cache.json`:

1. **16766 root cause is cue underspecification.** `synth_cache["sympy__sympy-16766"]["localization_cues"]` = 4 abstract cues; `verifications` = 4 concrete repros (basic Indexed, multi-dim, symbolic index, compound). Across 6 verify rounds in good_loop / good_multi_loop transcripts, the suite shows `[PASS] basic` and `[FAIL]` on the other 3 — the model fixes one site and stops.

2. **15976 root cause is edit-parser truncation.** Across 5 arms × 3 samples for 15976, 9/10 "no-block" notes (`runs_v2/sympy__sympy-15976__*gemma4_e4b*/transcript.json:notes[]`) begin with `` ```edit\nsympy/printing/mathml.py\n<<<<<<< SEARCH\n... `` and have no closing fence in the captured prefix. In `good_multi_loop__s0` turns 5–8, the model emits the **identical** truncated block 4 turns in a row because `_NO_BLOCK_HINT` advises "emit a bash block" rather than diagnosing the truncation.

3. **`OllamaLLM.max_tokens=8000`** (`harness/llm_ollama.py:54`) is the most plausible mechanical cause of the truncation class. Raising it is orthogonal but complementary to the parser fix; the parser fix is primary because (a) the budget is also legitimately bounded and (b) the parser must handle other fence-tag spellings too.

4. **Router self-improvement loop already works at sample-level outcomes.** `pipeline/router.py:RuleRouter.select` returns a ranked list; `pipeline/router.py:KNNRouter` learns from sample-level outcomes (394 rows). Both expose `select(features, model_slug, k=N)` and can supply a `select_arm_for_sample` method that operates on the same ranking + an in-trial history dict.

5. **Anti-leak primitives reusable as-is.** `memory/to_memory_entry.py:scrub_leak` + `gold_added_lines(iid)` are the canonical defense; `memory/synthesize.py:_extract_json` + `_scrub_entry` are the reusable JSON/scrub pipeline.

6. **`_synth_entry` is the single reader for cue content** (`pipeline/arm_context.py`); `extract_features` reads the top-level flat fields directly. The aliasing contract (top-level fields = `revisions[-1]` values) lets both readers stay untouched as long as refinement always overwrites the aliases after appending a new revision.

## Glossary

Canonical labels for cross-document consistency. Rejected variants in parentheses.

| Concept | Canonical label | Rejected |
|---|---|---|
| Subsystem 1 | **Outcome-Driven Cue Refinement** | "outcome-driven knowledge refinement" (too broad — knowledge ≠ cues), "knowledge self-improvement" (vague) |
| Subsystem 2 | **Lenient Edit Parser** | "two-tier extractor" (mechanism, not concept), "edit-format fix" (vague) |
| Subsystem 3 | **Adaptive Sample Rotation** | "adaptive sampling budget" (we don't change budget, we redirect samples), "sample-level routing" (too generic) |
| Refinement CLI | **`memory/refine_from_outcomes.py`** | (both research agents agreed) |
| Rotation arm | **`good_rotate`** | "adaptive arm" (no semantic gain), "router rotation arm" (redundant) |
| Per-sample picker | **`select_arm_for_sample`** | extending `select_arms` with `sample_idx` (overloads existing signature semantically; returns list vs single arm differs) |
| Cue lineage container | **`revisions: list[dict]` + top-level alias fields** | sibling file `synth_cache_v2.json` (two sources of truth), `active_revision` integer index (redundant with `revisions[-1]`) |
| Stuck task | **`(model_slug, iid)` where every arm resolved 0/k AND failure_count ≥ min_failure_count** | "all-arm failure" (ambiguous about model_slug), "zero-win task" (collides with KNN feature name) |
| Doom-loop | **Doom-loop**: model re-emits an unparseable edit block multiple turns because `_NO_BLOCK_HINT` is wrong advice for an edit-block failure | "edit oscillation" (vague), "parser-feedback mismatch" (verbose) |
| Decision branches | **REPLAY_WIN · FRESH_ARM · EXHAUSTED_RANKING · BURN_REPLAY** | "diversification cap K=2 then freeze" (conflates two branches; K=2 cap is over-conservative at k=3) |

## Requirements

**Functional**

1. `memory/refine_from_outcomes.py` reads `_oracle/outcomes_log.json` + `runs_v2/*/transcript.json`, identifies stuck tasks for a target `model_slug` (default `gemma4_e4b`), calls Opus with the existing cue entry + a leak-scrubbed failing-evidence digest, and appends a new revision to `_oracle/synth_cache.json` per task. Idempotent; per-task isolated; `--redo` forces re-refinement.
2. `harness/prompts.py:extract_edits` recovers SEARCH/REPLACE blocks whose closing ` ``` ` is missing or whose fence tag is non-`edit`. The fast path is preserved for well-formed input.
3. `harness/agent_loop.py` adds a third branch between the edit/diff branches and the `command is None` fallthrough: when `looks_like_edit_intent(text)` is true but no edit parsed, emit `_EDIT_MALFORMED_HINT` (with `diagnose_edit_block(text)` interpolated) instead of `_NO_BLOCK_HINT`.
4. `pipeline/router.py` adds `select_arm_for_sample(features, model_slug, sample_idx, tried_arms_results)` to both `RuleRouter` and `KNNRouter`. Decision branches: REPLAY_WIN → FRESH_ARM → EXHAUSTED_RANKING → BURN_REPLAY.
5. `pipeline/arm_context.py` adds a `good_rotate` arm that reads prior `runs_v2/` results for the same `(iid, model_slug)`, calls `select_arm_for_sample`, and delegates to the chosen sub-arm. Records `routed_from`/`routed_to`/`rotate_sample_idx`/`rotate_tried_history` in `arm_meta`.
6. `pipeline/orchestrator.py` schedules `good_rotate` cells in a per-`(iid, model)` chain so sample N+1 sees sample N's outcome on disk. Other arms keep the existing flat thread pool.
7. `pipeline/router.py` adds `evaluate_offline_rotate(router, k=3)` simulating `good_rotate` against the existing outcomes log under LOO.

**Non-functional**

- **Anti-leak**: refinement Opus never sees gold patches, hidden test paths, or test file content. Refined entries pass through `scrub_leak` against `gold_added_lines(iid)`; `leak_lines_removed` recorded per revision.
- **Backwards-compat**: every existing test in `harness/tests/test_search_replace.py` passes unchanged. Existing arms (`good`, `good_synth`, `good_loop`, `good_multi_loop`, `good_router`) read `synth_cache` via the aliased top-level fields and are unaffected by `revisions` being present.
- **Performance**: test suite total wall time ≤ 2s (current ~1.5s). No new external dependencies.
- **Per-revision lineage**: every refinement records `rev`, `parent_revision`, `created_at`, `source`, `model`, `leak_lines_removed`, `failure_evidence_count`, `stuck_criterion`, `refined_from`, `change_rationale`.

**Out of scope (deferred)**

- Direction B (learn verifications from outcomes) — verifications work correctly; cues lag verifications. Inverting is lower leverage.
- Direction D (outcome-pattern task clustering) — 17 tasks too small for unsupervised clustering.
- Direction E (cross-arm transcript routing) — subsumed by Subsystem 1's transcript harvest.
- Raising `OllamaLLM.max_tokens` — orthogonal complementary lever; not required for the parser fix to work.
- `cues_rev` field on outcomes log rows — flagged as an open question for the future; the directory-archive convention is the v1 versioning mechanism.

## Rationale

**Why three coupled subsystems instead of one big change**: the two unsolved tasks fail for *different reasons* (cue underspecification vs edit-parser truncation). A single intervention against one class would leave the other untouched. Subsystem 3 (`good_rotate`) is the smallest forward-looking addition: it costs nothing when no arm dead-ends and gains union benefit when one does.

**Why `revisions: list[dict]` over mutation or sibling file**: preserves before/after signal (the whole point of the experiment); single reader path; alias contract keeps `extract_features` and existing arms untouched.

**Why a separate `select_arm_for_sample` method rather than extending `select_arms`**: different semantics (returns one arm, not a ranked list; conditioned on in-trial history that has no equivalent in the static-pick path). Overloading `select_arms` would force every existing caller to opt into the new conditioning logic; a parallel method is cleanly opt-in.

**Why filesystem-coupled `good_rotate` instead of threading prior results through code**: matches existing pattern (every cell is self-describing on disk); survives orchestrator restarts; the only cost is requiring serial scheduling within a `(iid, model)` chain, which is a small wall-time loss bounded by `args.workers` concurrent chains.

**Why preserve the doom-loop's 6-strike parse-failures cap**: a buggy lenient parser must not become an infinite-retry loop. `consecutive_parse_failures` still increments on the new edit-malformed branch; episode still aborts with `stop_reason="parse_failures"` after 6 consecutive failures.

**Numeric thresholds — why these values:**

- **`min_failure_count = 3`**: the current eval runs k=3 samples per arm. The 4 runtime arms × 3 samples = up to 12 attempts per task per model. A floor of 3 failures requires at least one full sample-set of misses on at least one arm — strong enough that the model demonstrably struggles with the cues, not just an unlucky sample. Lower (1-2) admits flaky-sampling false positives; higher (6+) misses partially-stuck tasks where one arm wins occasionally.
- **`max_turns_per_run = 4`**: the harvested per-run digest takes the last 2 executed turns' stdout/stderr plus up to 2 parse-failure notes. Four observation entries × ~200 chars each × ~12 failing runs at the median = ~10 KB of failure evidence per Opus prompt — fits the existing `claude -p` payload budget that `memory/synthesize.py` already proves works.
- **`--max-tasks 10`**: bounds a single refinement batch to roughly one Opus call burst (≤ 10 × ~30s = ≤ 5 min wall time). Operationally it forces a cron cadence rather than a per-report trigger and caps the on-disk diff size on the synth_cache.json revision append; 10 is the order-of-magnitude budget for a once-daily refinement pass over the current 17-task suite.
- **`--workers 2`**: Opus calls dominate; 2 concurrent calls give parallelism without the rate-limit risk that 4+ would incur (precedent: `memory/synthesize.py:4` workers was acceptable on the smaller-prompt synthesis; refinement prompts are larger).
- **`--timeout 360`**: synthesize.py median is 15-20 s; refinement prompts are 3-5× longer; 360 s tolerates a 20× outlier safely. Below 180 s risks hard-failing legitimate slow calls.
- **`200 chars truncation`** on per-turn observations: matches the existing `episode.notes` 300-char cap (`harness/agent_loop.py`), 200 chosen as the smaller "evidence packet" form so 12+ failing runs fit one prompt.
- **`50_000-row` soft guard on outcomes_log size**: ~100× the current expected size (≤ 408 rows on the present setup). Trigger fires at production scales we have not designed for; intentional fail-fast, not a routine bound.

## Detailed Design

See:

- `architecture.md` — file map, function signatures, data flow, schema diffs.
- `bdd-specs.md` — Gherkin scenarios across 5 features (36 total: 10 refinement + 10 parser-lenient + 5 parser-feedback + 8 rotation + 3 rotation-offline-eval).
- `best-practices.md` — anti-leak contract, performance budget, common pitfalls.

## Design Documents

- [architecture.md](./architecture.md) — system layout, components, integration points, data flow diagram
- [bdd-specs.md](./bdd-specs.md) — full Gherkin scenarios (36 total; breakdown above)
- [best-practices.md](./best-practices.md) — anti-leak invariants, performance budget, pitfalls to forbid, comparison protocol
