# Architecture — Vision Roadmap

This is a *strategy* architecture: the units are pillars, tracks, gates, and a critical path, not classes and modules. Code anchors are cited so every routing decision is auditable.

## 1. Pillar routing

Each of the six vision pillars is routed to exactly one track by the deterministic rule:

- validated lift AND production gaps remain → **HARDEN**
- architecturally sound AND zero real traffic → **BOOTSTRAP**
- retrieval works AND fix-lift = 0 → **RESEARCH** (kill-gated, out of the pitch)
- no demonstrated value AND not on the critical path → **CUT**

| # | Pillar | Reflection score | Verdict | Evidence anchors |
|---|---|---|---|---|
| 1 | Shared memory layer exists | 8/10 | **HARDEN** | All 4 layers built (`service.py`: `contribute`, `search_problems`, `_resolve_book_solution`); gap is contract/trust/latency, already scoped as 18 PRs in `2026-06-02-pilot-readiness-design/_index.md`. |
| 2 | Knowledge extraction from strong models | 7/10 | **HARDEN** | Opus-distilled memories beat raw gold diffs (`_report/02_data.md`); production `synthesize_solutions` emits structured knowledge. Only the production path is unproven, and that is traffic-blocked, not extractor-blocked. |
| 3 | Weak-model same-task uplift | 8/10 | **HARDEN** (+ second domain, + executable phrasing) | Multi-model lift, zero harm (qwen 13/17→17/17; gpt-oss 1/17→6/17). **Caveat:** sympy-only, and the binding ceiling is the *execution gap* (gold-injected still 0–2/17, submit-rate 0.14–0.20, `_report/01_reflection.md`). Harden = broaden beyond sympy AND ship executable-phrasing payloads. |
| 4 | Agent contribution flow | 5/10 | **BOOTSTRAP** | `contribute`/`report_outcome` complete, but zero external traffic; flywheel needs ≥3 distinct external reporters (`confidence.py:89-90`). A traffic problem, not a build problem. |
| 5 | Auto-research worker | 6/10 | **BOOTSTRAP** (downstream of #4) | Outcome-gated hill-climber (`program.md:6`) sits on a flat 0.3 landscape with no external reporters (`confidence.py:65`) — nothing to climb. Unblocks the moment #4 delivers outcomes. Route together. |
| 6 | Cross-task transfer | 2/10 | **RESEARCH** (CUT from pitch now) | fix-lift +0 with an acted-on injection (`_report/04_cross_task_retrieval.md:111,120`); retrieval solved (55%) but irrelevant without application. One kill-gated look, then likely CUT. The shipped `pattern_class` leg is retained as plumbing. |
| — | ReviewerAgent quality gate | (off-pillar) | **CUT** | Dormant; `create_problem`/`create_solution` set `review_status="approved"` at write time. No value demonstrated, not on the critical path (`docs/principles.md` "ReviewerAgent" deferred decision). |

**Confirmed dependency (#5 ⟂ #4):** the worker keeps a proposal only if confidence strictly increases (`program.md:6`); confidence is identically `BASELINE_CONFIDENCE=0.3` when `unique_ext_reporters == 0` (`confidence.py:65`) and the author is excluded from external reporters — so with no external outcome flow every research candidate is a flat-baseline plateau. Sequencing pillar-5 work before traffic exists is wasted motion.

## 2. Track architecture

### Track H — Harden the validated core

**Goal:** make same-task recall a service a real adopter can rely on without surprises.

1. **Execute the pilot-readiness design** (`2026-06-02-pilot-readiness-design`). It already covers reflection top-actions 1–4. Of its 18 PRs, three are load-bearing prerequisites for Track B: **PR-6** (write-time dedup on an embedding-independent error-signature leg), **PR-9/PR-10** (sub-1s async-embed latency), **PR-1/PR-14** (REST/MCP parity + no false "strong" match on solution-less problems).
2. **Generalize the lift to a second domain.** The validated lift is sympy-only. Reproduce `same_task_lift ≥ +0.15` with `paired_harm == 0` on a held-out set in a *different* domain. A domain-narrow proof does not clear the bar (see `bdd-specs.md` pillar-routing second scenario).
3. **Narrow the execution gap.** Ship executable-phrasing payloads (the `localization_cues` → concrete-site enumeration pattern already proven in `2026-05-27-outcome-loop-design`). Agentbook cannot close the execution gap, but it owns "phrase the answer so a weak agent can land it."

**Exit bar:** hardened contract passes all `bdd-specs.md` parity/silent-failure scenarios with zero regressions, AND same-task lift `≥ +0.15` / `paired_harm == 0` reproduced in a second domain.

### Track B — Bootstrap the flywheel (escape cold-start)

A single-player-before-multiplayer sequence. **Instrument before you seed.**

- **Stage 0 — Domain selection by recurrence.** A domain is high-recurrence iff its bugs have **stable error signatures** AND a **shared upstream cause** AND **reproducible fixes**. Candidates: framework version-migration breakages, common dependency/build/deploy failures, a popular library's documented footguns. (Those three conditions are *also* exactly what sandbox-verified seeding needs — the domains that bootstrap cleanly and the domains that have organic recurrence are the same domains.) Avoid application-logic / business-logic bugs: each is unique, organic RD ≈ 0.
- **Stage 1 — Instrument recurrence, then seed verified trust.** Ship the recurrence instrument (§3). Build the corpus with the existing toolchain (`build_seed_corpus.py`/`corpus_synth.py`, gold-patch-backed). For every seed solution with an `error_signature` and a runnable repro, call `verify_solution` so the sandbox *executes* the fix → a real `kind="verified"` outcome → confidence up to `SANDBOX_ONLY_CEILING=0.6` (visibly above the 0.3 baseline, honestly below full confidence until real usage corroborates).
- **Stage 2 — Close one adopter loop.** One runtime (internal Claude Code or the eval harness's weak model), one real identity, recall-first on every error: hit → apply reliance target → report a genuine `observed` outcome (lifts the 0.6 cap toward full confidence); miss → solve unaided → `remember` (dedup steers near-matches to improve-mode). The worker hill-climbs / synthesizes once ≥2 active solutions exist. This is the loop that turns pillar 5 on.
- **Stage 3 — Open multiplayer, gated on organic recurrence.** Add a second independent adopter only after organic recurrence clears the green-light bar — never on calendar time.

**Exit bar:** a seeded domain measures `recurrence_density ≥ 0.30` over N=100 real incoming queries AND the adopter loop drives ≥1 solution above `COLD_START_FLOOR` (0.5) via `distinct_external_reporters ≥ 3` (no faked/self identities).

### Track R — Research cross-task transfer (kill-gated, off the product narrative)

One bounded ablation that isolates the single untested confound the L1 run left open (full sibling synth vs *abstract pattern alone*), on a weak and a strong model. Detailed in §4. **Cross-task transfer makes no product claim until this gate is passed; the likely outcome is a formal CUT.**

## 3. The recurrence-density instrument (new — the linchpin)

Today `search_problems` / MCP `recall` already compute `match_quality` and `no_good_match` per query but **persist nothing about the query**. Add an append-only query-log leg in the Application layer (mirrors the existing `_dedup_advisory` tiering, ~zero cost) recording per incoming query:

```
query_hash, reporter_or_ip, top_match_quality, has_help (reliance target != null),
matched_solution_author == querier?, pattern_class_hit?, timestamp
```

Derived, surfaced on the existing operator dashboard (`/v1/dashboard/...`):

- **recurrence density (RD)** = strong/exact hits with help, querier ≠ contributor, over independent queries (self-replay deduped by identity/IP). Excludes seed-replay so it cannot be self-inflated.
- **organic recurrence** = of strong hits, the share matching a *different agent's* contribution — the true network signal.

This is the instrument that lets a bad domain be killed within days of opening Stage 2 rather than after months of seeding. Ordering is non-negotiable: **instrument first, seed second** — otherwise seeded hits cannot be separated from organic recurrence (the `recall_simulation.json` `hit_rate:1.0` trap).

### Staged recurrence gates

| Gate | Metric | Threshold | Action |
|---|---|---|---|
| Stage 1→2 proceed | recurrence_density | ≥ 0.30 over N=100 independent queries | proceed to pilot same-task-lift gate; else abandon domain, re-pick |
| Domain kill | organic recurrence | < ~5% sustained after the loop runs on real tasks | domain dead — re-pick (don't seed more to "rescue" it) |
| Thesis kill | organic recurrence | < ~5% across 2–3 *chosen high-recurrence* domains | the same-task *network* thesis fails → pivot to a bundled single-player verified-corpus product |
| Multiplayer green-light | organic recurrence | ≥ ~15% and rising as entries accumulate | open to independent adopters; invest in growth |

N=100 gives a ±~9% binomial CI at p=0.30 — enough to separate a viable domain from a near-zero one without demanding production-scale traffic.

## 4. The kill-gated cross-task experiment

**Name:** `abstract_loop` ablation — does *pattern-only* + explicit re-derivation beat control, on a weak and a strong model?

**Hypothesis (falsifiable):** injecting *only* the sibling's abstract `root_cause_pattern` + `root_cause_class` (concrete `localization_cues`/`verification` **stripped**, since those point at the *other* bug's code and act as distractors), plus the instruction *"this is a related-but-different bug; do not look for the named symbols — re-derive where THIS bug manifests the pattern and fix it here,"* produces fix-lift over control. H0: it does not.

**Arms (4), shared task-own verify loop, only injected knowledge differs:**

| arm | injected | role |
|---|---|---|
| `control_loop` | none | baseline (reproduce 1/13) |
| `sibling_loop` | full sibling synth (pattern + cues + verification) | reproduce the published +0 anchor |
| `abstract_loop` | sibling `root_cause_pattern` + class only + re-derive instruction | **the treatment** |
| `good_loop` | task's OWN full synth | positive control (must reproduce ~+6) |

**Model-strength axis (within eval policy):** weak = `gpt-oss:20b` local (matches the published negative result exactly); strong = internal cloud qwen (the only permitted cloud model). The strong arm tests the premise itself — per the meta-learning literature, if re-derivation works anywhere it works on the stronger model first. If even the strong model is flat, the premise is dead regardless of the weak-model target.

**Design:** 13 tasks (frozen LOO set) × k=5 × 4 arms × 2 models = 520 cells. Powered to detect a *large* effect only — deliberate; a small effect is treated as a kill.

**Metric:** paired fix-lift = `abstract_loop` pass@5 − `control_loop` pass@5, per model track. Diagnostics (non-gating): submit-rate, a harm counter (control PASS → abstract FAIL = distractor damage), and the count of abstract cells that submit a patch.

**Reuses existing plumbing:** `pipeline/orchestrator.py:_has_memory`, `pipeline/arm_context.py:_taxonomy_sibling`, `_oracle/taxonomy_siblings.json` — one new arm builder (pattern fields only + swapped instruction).

**Success vs kill** — see the cross-task kill gate in `bdd-specs.md`. Success = `abstract_loop − control ≥ +3/13` on *either* track AND `abstract_loop ≥ sibling_loop`. Pre-committed kill = `≤ +1/13` on *both* tracks → formal CUT. Validity gate = `good_loop − control ≥ +4/13` or the run is void (a broken harness cannot trigger a false kill).

## 5. Dependency graph & critical path

```
Track H (pilot-readiness PRs)
  ├─ PR-6 dedup ─────────────┐  (prerequisite: makes recurrence visible)
  ├─ PR-9/10 latency         │  (recall-first dies at 4–8s)
  └─ PR-1/14 parity+honesty  │
                             ▼
                   Recurrence instrument (NEW, §3)   ← instrument BEFORE seed
                             │
                             ▼
Track B:  Stage 0 pick domain → Stage 1 seed+verify → Stage 2 closed adopter loop
                             │                              │
                   RD ≥ 0.30 gate ────────────────► pilot same-task-lift gate
                             │                              │
                             ▼                              ▼
                   organic-recurrence gate ──────► Stage 3 multiplayer
                             │
                   (also: Stage 2 outcomes ⇒ worker activation, pillar 5 turns on)

Track R (parallel, OFF critical path, OUT of product narrative):
  build abstract_loop arm → 520-cell run → kill gate → continue | CUT
```

**Critical path = H (dedup + latency + parity) → recurrence instrument → B.** Track R is independent and must never block H or B, never enter the product narrative until its gate passes, and is funded once (no reopen-by-prompt-tweak). Pillar 5 (worker) is not separately scheduled — it activates as a side effect of Stage 2 outcome flow.

## 6. What this architecture deliberately does NOT do

- It does not re-plan the pilot-readiness PRs (referenced, not duplicated).
- It does not add network features, forum/token economy (dropped — see `CLAUDE.md` Database), or new transports before recurrence is proven.
- It does not promise cross-task fix value anywhere user-facing.
- It does not schedule worker improvements ahead of outcome traffic.
- It does not seed before the recurrence instrument exists.
