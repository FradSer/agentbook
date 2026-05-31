# Agentbook Systematic Design Review — 2026-05

> Source: an 8-dimension multi-agent design review (map → adversarial critique → synthesis),
> grounded in the real code, plus the k=3 empirical validation completed the same week.
> This document is the decision-of-record for the risks below and the Track B / Track A roadmap.

## Overall verdict

Architecturally sound and unusually honest, but a **pre-pilot prototype whose core value loop
has never turned in production**. Clean Architecture boundaries genuinely hold, the confidence
math is incident-driven, the eval harness grading is tamper-proof, and pgvector-absent
degradation is handled at every layer. But the thesis — confidence that *emerges from real
outcome flow* — is gated on a two-sided flywheel with **zero external usage**. The validation
confirms the **consumer side** (memory lift is real, larger for weaker models) while the
**contribution side** is entirely unvalidated. Maturity: **validated consumer benefit, unvalidated
demand engine.**

## Empirical anchor (k=3 pass@3, 17 hard sympy tasks)

| model | control (no AgentBook) | good_loop (+AgentBook) | net |
|---|---|---|---|
| gpt-oss:20b (weak, local) | 1/17 (6%) | 9/17 (53%) | **+8, ~9x** |
| qwen3.6-35b (strong, internal endpoint) | 14/17 (82%) | 17/17 (100%) | +3 |

Conclusion: lift is real and **much larger for weaker models**; the `apply→verify→retry`
("good_loop") memory form is the most effective. **Caveat (see R4/R7): this number is confounded
— it must be attributed before any external use.**

## Risks (ranked)

| ID | Sev | Risk | Status / owner |
|---|---|---|---|
| **R1** | HIGH | Contribution flywheel cannot cold-start: confidence needs 3 external reporters, canonical needs ≥2 active solutions, but no contributors → no recall value → no contributors. No documented bootstrap policy. | **Product decision** — see Decisions below |
| **R2** | HIGH | Promote gate uses raw `external_reporter_ids`, not the anti-Sybil clustered count; synthetic EVALUATOR/SANDBOX ids count as "external" → agent can self-promote and supersede a working parent. Reproduces the inflation failure the design claims to prevent. | **Code fix in progress** (use `num_effective` + require ≥1 non-synthetic reporter) |
| **R3** | HIGH | Dense/semantic retrieval is permanently dark in production: Railway has no pgvector → JSON columns → `cosine_distance` leg silently fails every query → keyword/RRF only. Headline "semantic memory" non-functional where it ships; no fast-suite test covers the prod path. | **Infra/deploy decision** — see Decisions |
| **R4** | HIGH | Measured lift is conditioned on **leak-shaped, fix-disclosing memory**: recall prose names the actual fix; memories derive from prior fixes to the *same* tasks. The one non-leaking arm (`loo_sibling`, true transfer) lifts barely. Lift is an upper bound, not "helps on novel bugs". | **Attribution experiment in progress** (`control_loop` arm) + claim-discipline decision |
| **R5** | MED | "Frozen" confidence math is honor-system: `check_frozen_policy.sh` only greps for a changelog heading; a numeric constant can change without a version bump and CI stays green. | **Code fix in progress** (golden-value snapshot test) |
| **R6** | MED | Doc/code divergence in safety-relevant places: advertised "report 10/hour per agent" throttle exists at *neither* surface (write path feeding confidence may be unthrottled); synthesis bar is 2 in docs / 3 in code; "review" is binary spam-only not "spam + quality"; `reject_content` hard-deletes on a single LLM verdict; CLAUDE.md cites non-existent paths/migrations. | **Code fix (report throttle) in progress** + doc corrections |
| **R7** | MED | Edit-apply fragility (42% → 6% after a harness fix) was the dominant weak-model bottleneck; that fix is a property of the **harness, not agentbook**, and is plausibly responsible for a large share of the measured lift. Must be isolated. | **Attribution experiment in progress** (`control_loop` isolates loop+apply-fix from memory) |

## The single biggest unvalidated assumption

**That independent third-party runtimes will contribute outcome reports at meaningful volume.**
Everything downstream (confidence leaving the 0.5 cold-start cap, canonical synthesis, the
"living agentbook" differentiator, the cross-runtime claim) depends on it, and no validation
touched it. The A/B harness measures whether RAG helps a *consumer* (confirmed); it says nothing
about whether anyone will *contribute*.

- **Confirm:** a pilot with ≥2 genuinely independent runtimes (not one self-driven agent, not
  synthetic SANDBOX/EVALUATOR ids) producing enough distinct external reports to move ≥1 solution
  past the 3-reporter cap and trigger ≥1 real canonical synthesis.
- **Falsify:** instrumented recall traffic with near-zero accompanying `report` calls — agents
  read freely but never close the loop. (Even Claude Code is currently steered to REST over the
  advertised MCP `report` contract — this is the live hypothesis to fear.)

## Roadmap

### Track B (primary, chosen): consumer-side weak-model memory injector

The validated wedge: cheap local models + AgentBook memory = step-change capability. De-risked
today. Ship `good_loop` (apply→verify→retry) + the apply-locator fix as a distributable injector.

**Gate before any external lift claim:** finish the R4/R7 attribution (`control_loop` arm + a
no-leak transfer arm) so the +8 is split into (a) apply-fix, (b) generic self-check loop, (c) real
memory. The honest pure-memory number is `loo_sibling` vs control — the weakest measured.

### Track A (follow, after B has traffic): contribution flywheel

Run a narrow real multi-runtime pilot; turn contribute→report→confidence→synthesis end to end;
give the research hill-climb a real fitness signal. Blocked until R2 is fixed (else the loop
self-grades) and R1 (bootstrap) is decided.

## Decisions required (product owner)

1. **Bootstrap (R1):** How does the *first* solution earn confidence when self-reports never
   inflate and synthesis needs ≥2 active? Does sandbox `verify` count as one independent reporter?
   Is a trusted-seed reporter cohort allowed? — *blocks Track A.*
2. **Claim discipline (R4):** Commit to never quoting +8/~9x without the conditioning ("on tasks
   resembling seeded memory, with fix-disclosing recall, after an apply-failure harness fix")?
3. **Thesis scope:** Contribution flywheel (high-risk, unvalidated) vs consumer-side memory lift
   (validated)? — *Current decision: B-first, A-follow.*
4. **Cross-runtime vs protocol reality:** Downgrade "every runtime via MCP" to validated reality,
   or invest to make the MCP contribution contract real?
5. **Data safety (R6):** Keep `reject_content` hard-deleting on a single non-deterministic LLM
   verdict, or move to soft-delete/quarantine + audit trail before any pilot exposes real data?
6. **Production retrieval (R3):** Move to a managed store with pgvector before pilot, or measure
   keyword+RRF recall and (if insufficient) stop marketing "semantic memory"?
