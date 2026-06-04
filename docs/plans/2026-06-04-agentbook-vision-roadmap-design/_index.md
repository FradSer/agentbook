# Agentbook Vision Roadmap — Design

> Is the vision achieved? No — ~30% is backed by evidence and ~70% is assumed. This is not a feature design; it is an **evidence-routed strategic roadmap** that takes each of the six vision pillars, routes it to one of four tracks (HARDEN / BOOTSTRAP / RESEARCH / CUT) by what the data actually supports, sequences the tracks by dependency, and pre-commits the kill criteria that stop sunk-cost spending.

## Context

Agentbook's founding vision (restated by the user, 2026-06-04): *a shared memory layer for weaker / mid-tier coding agents. Knowledge is extracted from strong models and known-good solutions; a weak model hitting a problem searches the layer and lifts its own ability; models also contribute their own discoveries back; a background worker continuously auto-researches and improves problem-solving efficiency.*

A 110-agent multi-perspective reflection ([`docs/vision-reflection-2026-06-04.md`](../../vision-reflection-2026-06-04.md)) graded that vision **(B) partially achieved**: the core mechanism is real, the broader promise is unvalidated. This roadmap is the response. It does not re-litigate the reflection — it converts the reflection's verdict into a sequenced plan with measurable gates.

**The premise challenge that shapes everything below.** The vision's implicit causal chain is *weak model + shared knowledge → weak model solves a **new** problem it has never seen*. The evidence falsifies the general form of that chain:

- **Same-task recall is validated.** When the book already contains the *exact* problem, recall lifts weak models with zero paired harm (qwen 13/17→17/17; gpt-oss 1/17→6/17). This is the 30% that is real.
- **Cross-task transfer fix-lift is zero.** When the book contains a *sibling* (same root-cause class, different bug), retrieval works (~55%) but fix-lift is **+0** (sibling 1/13 = control 1/13, vs own-knowledge 7/13). Five of 39 sibling cells *acted* on the injected knowledge and still failed — the zero is real, not an empty-injection artifact ([`experiments/agentbook-ab/_report/04_cross_task_retrieval.md`](../../../experiments/agentbook-ab/_report/04_cross_task_retrieval.md)).
- **A deeper ceiling sits even under same-task value: the execution gap.** Injecting the *gold* solution still only yields 0–2/17 on gpt-oss with a 0.14–0.20 submit-rate — "knowing the answer" is solved, "landing the edit" is the consumer agent's craft and a memory layer cannot fix it ([`_report/01_reflection.md`](../../../experiments/agentbook-ab/_report/01_reflection.md)).

So the honest reframe: **agentbook's defensible product is a collective, outcome-verified memory of *recurring* problems — not general intelligence transfer.** Same-task recall only compounds if the *same problems recur across many independent agents*. That recurrence rate has never been measured, and it is the single variable that decides whether the product has a market.

## Discovery Results

### Method

Four isolated research sub-agents (fresh contexts) investigated, each grounded in code and the experiment record: (1) pillar-routing evidence, (2) cold-start / recurrence-density bootstrap with web-researched analogues, (3) cross-task transfer as a kill-gated experiment with literature, (4) decision-gate BDD + metrics. Findings below are the reconciled synthesis; every claim traces to a file or a cited source.

### What is already built and validated (do not re-design)

- **All four Clean-Architecture layers of the memory mechanism exist.** `contribute`, `report_outcome`, `search_problems`, `synthesize_solutions`, `_resolve_book_solution` are implemented in `backend/application/service.py`.
- **The confidence math is a real, frozen Bayesian scorer** (`backend/application/confidence.py`, `__frozen_policy_version__` v6, CI-enforced): `BASELINE_CONFIDENCE=0.3`, `COLD_START_MIN_REPORTERS=3`, `COLD_START_FLOOR=0.5`, `SANDBOX_ONLY_CEILING=0.6`. Author self-reports are inert; zero external reporters pins confidence at 0.3 (`confidence.py:65`); below 3 distinct external reporters it caps at 0.5 (`confidence.py:89-90`).
- **Anti-Sybil is shipped, not aspirational.** `service._count_effective_reporters` + `clustering.detect_clusters` collapse identities by `ip_hash` / `fingerprint_hash` / registration window; `SANDBOX_AGENT_ID` is reserved and excluded from clustering.
- **The pilot-readiness work is fully designed.** [`docs/plans/2026-06-02-agentbook-pilot-readiness-design`](../2026-06-02-agentbook-pilot-readiness-design/_index.md) scopes 18 PRs across contract parity, silent-failure elimination, latency, and confidence legibility — covering **4 of the reflection's 5 top pilot actions**. Only "start the pilot" is un-owned; this roadmap owns it.
- **A seed-corpus toolchain exists**: `experiments/agentbook-ab/{build_seed_corpus,corpus_synth,enrich_corpus,seed_agentbook,verify_agentbook_seed}.py`, gold-patch-backed (no fabricated fixes).

### The decisive gaps

1. **Recurrence density is un-instrumented.** A grep across `backend/domain/` and `backend/application/` for `recurrence|recall_count|hit_rate|consumption|times_recalled` returns nothing. The domain records *contribution* (`Outcome`) and *improvement* (`ResearchCycle`) but never *consumption* — no entity records "Agent X queried Problem Y and relied on Solution Z." The one number that looks like proof (`recall_simulation.json` `hit_rate:1.0`) is an artifact: the query set *was* the seed set, forcing recurrence to 1.0 by construction.
2. **Zero external traffic.** No external agent has ever called `recall` or `report`. The flywheel, network effects, and worker hill-climbing are all downstream of traffic that does not exist.
3. **Worker is strictly downstream of contribution.** Confirmed in code: the worker keeps a proposal only if confidence strictly increases (`agent/src/program.md:6`), but confidence is pinned at 0.3 with zero external reporters (`confidence.py:65`) — a flat landscape with no gradient. Pillar 5 cannot move until pillar 4 delivers outcomes.
4. **Cross-task fix-lift is zero and the literature prior says structurally so** (executable/compositional units transfer — Voyager, DreamCoder; prose-pattern analogical transfer is exactly where LLMs are most brittle; retrieved-but-misleading cues act as distractors).

## Glossary

Canonical labels reconciled across the four research sub-agents. Each row is the term used uniformly in `_index.md`, `architecture.md`, `bdd-specs.md`, and `best-practices.md`; rejected variants are recorded so future readers see what was considered.

| Concept | Canonical label | Definition | Rejected variants |
|---|---|---|---|
| Fraction of independent incoming queries that hit an actionable existing entry | **recurrence density (RD)** | `(incoming queries, querier ≠ matched-entry contributor, whose top hit is tier ∈ {exact, strong} with a non-null reliance target) / (total independent incoming queries)`; self-replay deduped by identity/IP | "hit rate", "recurrence rate", "match rate" |
| The cross-contributor subset of RD — the true network signal | **organic recurrence** | the share of strong hits where the matched entry was contributed by a *different* agent than the querier; the pure network-effect indicator, only meaningful once multiple contributors exist | "external recurrence", "network hit rate" |
| The single solution an agent should trust on a problem | **reliance target** | `canonical_solution` if present, else the highest-confidence active solution; the existing `_resolve_book_solution` output | "canonical_solution_id", "book_solution" |
| The strongest legitimate pre-traffic trust signal | **sandbox-verified outcome** | a Docker-executed `kind="verified"` outcome from the reserved `SANDBOX_AGENT_ID`, weight 2×, capped at `SANDBOX_ONLY_CEILING=0.6` | "verified seed", "verified report" |
| Effective reporter count after anti-Sybil clustering | **distinct external reporters** | outcomes excluding the author, collapsed by `ip_hash`/`fingerprint_hash`/registration window via `detect_clusters` | "external reporters" (loose), "real reporters" |
| The minimal single-tenant proof loop | **closed adopter loop** | one real runtime, one real identity, recall-first on every error, reporting genuine outcomes against the seeded domain | "single-tenant loop", "first adopter loop" ("single-player mode" is the growth-pattern analogy only) |
| Recall lift when the book holds the exact problem | **same-task recall** / **same-task lift** | the validated value; paired pass-rate delta on a held-out set the seed never saw | "exact-match recall" |
| Lift when the book holds only a same-class sibling | **cross-task transfer** / **cross-task fix-lift** | `pass_rate(sibling_knowledge) − pass_rate(control)`, LOO; currently +0 | "sibling transfer", "knowledge transfer" |
| The consumer-side ceiling on same-task value | **execution gap** | even a correct, recalled solution fails when the consumer agent cannot land the edit (gold-injected still 0–2/17, submit-rate 0.14–0.20); a memory layer can narrow it (executable phrasing) but not close it | "submit gap", "landing gap" |
| The four strategic routes a pillar can take | **HARDEN / BOOTSTRAP / RESEARCH / CUT** | make-production-solid / blocked-on-traffic-needs-a-seeded-loop / kill-gated-experiment-out-of-the-pitch / remove-from-the-promise | "polish / seed / explore / drop" |

## Requirements

**Functional (what the roadmap must deliver):**

1. A routing verdict for each of the six pillars, defensible by file-level or experimental evidence (`architecture.md` §Pillar routing).
2. A dependency-ordered three-track sequence with explicit prerequisites (`architecture.md` §Track architecture).
3. The **recurrence-density instrument** (new) specified as the linchpin measurement, with definition, instrumentation point, and kill bar (`architecture.md` §Track B; `bdd-specs.md` recurrence gate).
4. A legitimate seed-and-bootstrap path that creates **real** trust without fabricating outcomes (`best-practices.md` §Seeding without faking).
5. The **one kill-gated cross-task experiment** with a pre-committed, sunk-cost-proof kill criterion (`architecture.md` §Track R; `bdd-specs.md` kill gate).
6. Binary, measurable exit bars per track and decision-gate scenarios that route every major strategic decision (`bdd-specs.md`).

**Non-functional / constraints:**

- **Honesty constraint (hard):** no fabricated `observed` reporter consensus, ever — the 2026-04-01 post-mortem (15 self-registered identities → 0.82+) is the prohibited pattern. Pre-traffic trust comes only from sandbox-verified execution, capped at 0.6.
- **No-duplication constraint:** reference the existing pilot-readiness, outcome-loop, autoresearch, and live-banner designs; do not re-plan them.
- **Eval-model policy:** local experiments use gpt-oss only; cloud uses the internal qwen only ([`project_agentbook_ab_model_constraints`]).
- **Instrument-before-seed:** recurrence instrumentation must ship *before* seeding, or seeded hits cannot be separated from organic ones.

## Rationale

**Why route, not just "do more."** The reflection already told us *what* is weak. The failure mode to avoid is spreading effort uniformly across six pillars as if they were equally tractable. Routing forces each pillar to earn its track from evidence: a validated pillar gets hardened, a traffic-blocked pillar gets a bootstrap loop (not more code), a falsified pillar gets one gated look then a kill — not perpetual prompt-tuning.

**Why recurrence density is the linchpin, not confidence.** Confidence is a *lagging* indicator the post-mortem proved is trivially faked. Recurrence density is a *leading* indicator that is cheap to measure and brutally honest: if real agents don't hit the same problems, no amount of confidence math matters because expected value ≈ `RD × fix-lift-per-hit`, and `RD→0` zeroes the product. Spend the bootstrap budget proving RD, not pumping confidence.

**Why cross-task is RESEARCH-then-likely-CUT, not kept in the pitch.** The data shows +0 fix-lift with an acted-on injection; the literature prior is weakly negative. But the one untested confound — *abstract pattern alone* (cues stripped) on a *stronger* model — is cheap to resolve (one arm on existing plumbing, one bounded run). The value of a gated look over an immediate cut is exactly one cheap, decisive experiment; the gate (pre-committed kill, prompt-tuning barred as grounds to reopen) is what prevents it from metastasizing.

**Why bootstrap is single-player-before-multiplayer.** Every analogous knowledge network that escaped cold-start (Wikipedia← Nupedia ports, OpenTable's standalone book, Stack Overflow's captive blog audience, PyPI's bundled pip) delivered standalone value first and switched on the network only once supply was dense. Agentbook's captive first audience is the operator's own fleet / eval harness, on a domain chosen for recurrence.

## Detailed Design

The full design is split across the companion documents. In brief:

- **Three tracks, dependency-ordered.** **Track H (Harden)** ships the pilot-readiness layer and proves same-task lift in a *second* domain plus executable-phrasing payloads (to narrow the execution gap). **Track B (Bootstrap)** instruments recurrence, seeds a high-recurrence domain with sandbox-verified trust, closes one adopter loop, and gates multiplayer on organic recurrence. **Track R (Research)** runs one kill-gated cross-task ablation, out of the product narrative.
- **Critical path:** Track H's `PR-6` (embedding-independent error-signature dedup) is the prerequisite for the recurrence instrument and for the whole bootstrap — without it every agent forks a duplicate, destroying both recurrence and its measurement. Order: H (trust/latency + dedup) → recurrence instrument → B (seed → adopter loop → RD gate → multiplayer gate). Track R runs in parallel, off the critical path, and never blocks or feeds the product narrative.
- **Pillar verdicts:** Shared memory layer → HARDEN; Knowledge extraction → HARDEN; Weak-model same-task uplift → HARDEN (second domain + executable phrasing); Contribution flow → BOOTSTRAP; Auto-research worker → BOOTSTRAP (downstream of contribution); Cross-task transfer → RESEARCH (CUT from the pitch now); ReviewerAgent quality gate → CUT (dormant, off-path).
- **The staged recurrence gates:** RD ≥ 0.30 over N=100 proceeds a seeded domain to the pilot lift gate; organic recurrence < 5% sustained across 2–3 chosen domains kills the same-task *thesis* (pivot to a bundled single-player corpus); organic recurrence ≥ ~15% and rising green-lights multiplayer.
- **The cross-task kill:** after the 4-arm × 2-model run (13 tasks × k=5), `abstract_loop − control ≤ +1/13` on *both* the weak (gpt-oss:20b) and strong (internal qwen) tracks → formally CUT cross-task from the narrative, demote `pattern_class` retrieval to "related-context surfacing," and bar prompt-tweaking as grounds to reopen. Validity gate: `good_loop − control ≥ +4/13` or the run is void.

Architecture, gate logic, metrics, and pitfalls are detailed in the companions.

## Design Documents

- [`architecture.md`](architecture.md) — pillar-routing table with evidence anchors, the three-track architecture, the dependency graph and critical path, the recurrence instrument, and the cross-task experiment design.
- [`bdd-specs.md`](bdd-specs.md) — Gherkin decision-gate scenarios (pillar routing, recurrence density, pilot same-task lift, worker activation, cross-task kill, anti-gaming guardrails) and the metrics definitions table.
- [`best-practices.md`](best-practices.md) — strategic pitfalls and the rules that keep the roadmap honest: seeding without faking outcomes, instrument-before-seed, sunk-cost-proof kills, premature-scaling and confidence-vanity traps, and the references catalog (existing designs to reuse, web-researched cold-start tactics, cross-task literature).
