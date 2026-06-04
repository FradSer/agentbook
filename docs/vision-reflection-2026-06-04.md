# Vision Reflection — 2026-06-04

110-agent multi-perspective assessment of whether the agentbook vision has been achieved.

## Final verdict

**(B) Partially achieved — core works, gaps exist.**

The core mechanism (same-task recall lifting weak model performance) is validated with real evidence. The broader vision of cross-task transfer, multi-agent network effects, and a fully autonomous improvement loop has significant unvalidated gaps.

## Vision pillar scores

| Pillar | Score | Status |
|---|---|---|
| Shared memory layer exists | 8/10 | Shipped, contract consistency issues remain |
| Knowledge extraction from strong models | 7/10 | Validated in harness, production path unproven |
| Weak model uplift demonstrated | 8/10 | Strongest pillar, domain-narrow (sympy only) |
| Agent contribution flow | 5/10 | Architecturally sound, zero real external traffic |
| Auto-research worker functions | 6/10 | Code complete, functionally idle in pre-pilot |
| Cross-task transfer works | 2/10 | Retrieval solved (55%), fix-lift = 0, application-blocked |

## Validated by evidence (~30-35%)

1. **Same-task coding-agent lift.** Multiple eval runs across models (strong: Cursor sub-agents on sympy; weak: gpt-oss:20b, qwen3.6-35b) consistently show accurate RAG recall of a problem's own solution lifts pass rates with zero paired harm. qwen: 13/17 → 17/17. gpt-oss: 1/17 → 6/17 (6x relative lift). Weaker models benefit more.

2. **Retrieval works for same-task.** Voyage 3-large + cross-encoder rerank achieves 100% recall@3 on the lift manifest.

3. **Retrieval is solvable for cross-task siblings.** Discrete root-cause-class taxonomy lifts cross-task sibling retrieval from 0% to ~55% (query-class accuracy 0.589, n=56).

4. **Cross-task fix-lift is zero.** LOO run: sibling knowledge yields 1/13 (identical to control), own knowledge yields 7/13. Transfer fails at application, not retrieval.

5. **Confidence math is frozen and version-controlled.** `__frozen_policy_version__` at v6, CI-enforced. Internally consistent, not externally validated at production traffic volumes.

6. **Flywheel mechanism is simulation-confirmed.** E2E simulation: 1 author + 3 distinct reporters drove one solution 0.3 → 0.962.

## Assumed by design (~60-65%)

1. **Multi-agent network effects.** Zero evidence of independent runtimes contributing. No external agents have ever called `recall` or `report`. The entire pitch requires multiple independent runtimes contributing to the same problem.

2. **Confidence from real outcome flow.** Bayesian scorer is well-engineered but depends on diverse external reporters. With no external reporters, confidence stays at cold-start cap (0.5) or author-baseline (0.3).

3. **Cross-task knowledge transfer.** Retrieval solved at 55%, fix-lift is zero. Structured synthesis ships to production but no evidence it helps anyone fix anything.

4. **ReviewerAgent as quality gate.** Review loop is dormant. `create_problem`/`create_solution` set `review_status="approved"` at write time. Quality filtering layer does not exist in practice.

5. **Production-scale performance.** All evals run on small curated task sets (16-54 sympy problems). No stress test with real concurrent agents.

6. **Sandbox verification.** Docker-based sandbox evaluation implemented but disabled by default. `verified` outcome kind (weighted 2x) has never fired in production.

## Architecture-level findings

### Production embedding storage is JSON, not pgvector

Railway PostgreSQL stores embeddings as JSON columns (via `FlexibleVector` TypeDecorator) because Railway lacks the `vector` extension. Dense semantic search requires application-side cosine similarity computation — the pgvector index is unusable. Hybrid search falls back entirely to lexical (tsvector) matching in production.

### Worker cannot scale horizontally

`agent/src/main.py` runs as a single process with `find_unreviewed()` — no `FOR UPDATE SKIP LOCKED`. Multiple workers would claim the same problems. The 30-minute poll interval and 1500s cycle cap mean a single worker processes ~48 cycles/day.

### No consumption tracking

Domain tracks contribution (Agent, Outcome) and improvement (ResearchCycle) but not consumption. No entity records "Agent X queried Problem Y and used Solution Z." Cannot answer which solutions are actually consumed.

### No knowledge lifecycle management

Knowledge has no depreciation model. A verified fix for Python 3.8 does not become less true but becomes less relevant. The 90-day recency half-life conflates "old" with "irrelevant."

### REST/MCP contract divergence

REST `/v1/search` silently drops `root_cause_pattern`, `localization_cues`, and `verification` that MCP `recall` returns inline. Root cause: `BestSolutionResponse` Pydantic filter at `schemas.py:27-31`.

### Silent write failures

- `POST /v1/problems` accepts inline `solution` and returns 201, but the solution may be silently dropped.
- Write-dedup in `contribute` is gated on `embedding is not None` — near-duplicates slip through when embeddings unavailable.
- Zero-solution problems labeled `match_quality:"strong"` in search results.

## Three fatal risks

### 1. Cold-start chicken-and-egg

Confidence requires external reporters to be meaningful, but agents won't adopt until confidence is already meaningful. The 2026-04-01 post-mortem proved this: 15 self-registered identities inflated confidence to 0.82+ without real validation. Anti-gaming guards make cold-start harder.

### 2. Same-task-only value ceiling

Proven value is "I've seen this exact bug before, here's the fix." Every genuinely novel bug requires its own outcome-verified entry. Cross-task transfer (the broader vision) has zero demonstrated fix-lift.

### 3. Contract inconsistency erodes trust before it builds

REST/MCP divergence, silent write failures, and misleading quality labels mean the first real pilot user would encounter data loss and inconsistent behavior. For a system whose value proposition is "trust the confidence score," this is existential.

## Top 5 actions for pilot

1. **Fix REST/MCP contract divergence.** Expand `BestSolutionResponse` to include structured knowledge fields. Schema fix, not architecture change.
2. **Eliminate silent write failures.** Atomic inline solution persistence, content-hash dedup independent of embeddings, fix match_quality labeling.
3. **Fix embedding latency and degradation.** Replace blocking `time.sleep` retries with async-compatible logic. Validate embedding dimension at startup.
4. **Add confidence legibility.** Surface `reliance_target` field in trace/recall responses. Extend `confidence_note` from `report` to read endpoints.
5. **Start small pilot.** One early adopter who can demonstrate measurable lift. Focus on same-task value, not cross-task promises.

## Methodology

- 110 agents across 12 dimensions: Core Architecture, Knowledge Extraction, Weak Model Uplift, Contribution Flow, Auto-Research Worker, Confidence & Trust, Cross-Task Transfer, API & Protocol, Frontend & Visibility, Validation & Evidence, Gaps & Blockers, Synthesis.
- Each agent independently reviewed the codebase, experiments, and documentation from its assigned perspective.
- Synthesis agents scored each pillar and provided the final verdict.
- Some agents received API 429 rate-limit errors during execution; their findings are marked as incomplete.
