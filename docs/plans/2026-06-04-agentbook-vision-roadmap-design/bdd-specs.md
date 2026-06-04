# BDD Specs — Vision Roadmap Decision Gates

These are **strategic decision gates**, not feature tests. Each gate takes accumulated evidence as its `Given`, applies a pre-committed threshold as its `When`, and routes a strategy decision (HARDEN / BOOTSTRAP / RESEARCH / CUT / PROCEED / KILL) as its `Then`. They follow the project's house Gherkin style: a prose Feature preamble naming the canonical concept, then concrete Scenarios using real field names (`confidence`, `external_reporters`, `COLD_START_FLOOR=0.5`, `BASELINE_CONFIDENCE=0.3`) and real evidence anchors. Thresholds match the canonical values reconciled in `_index.md` Glossary and `architecture.md`.

## Gherkin decision-gate scenarios

```gherkin
Feature: Pillar routing gate — evidence routes each vision pillar to a track

  The roadmap is evidence-grounded: a pillar is not worked because it is in the
  vision, but because its current evidence earns a track. Each pillar from the
  2026-06-04 vision reflection carries a score and a validation status
  (validated-by-evidence / assumed-by-design). A routing decision maps that
  evidence onto exactly one track: HARDEN (validated core, make it
  production-solid), BOOTSTRAP (architecturally sound but zero real traffic —
  needs a seeded loop), RESEARCH (kill-gated experiment, kept out of the product
  narrative), or CUT (no demonstrated value, remove from the pitch). The routing
  rule is deterministic so the same evidence always yields the same track.

  Routing rule:
    - validated lift AND production gaps remain      -> HARDEN
    - architecturally sound AND zero real traffic    -> BOOTSTRAP
    - retrieval works AND fix-lift = 0               -> RESEARCH (kill-gated)
    - no demonstrated value AND not on critical path -> CUT

  Scenario Outline: A pillar is routed by its evidence, not its ambition
    Given the pillar "<pillar>" with evidence status "<evidence>"
    When it is measured against the routing rule
    Then it is routed to "<track>"
    And the routing rationale is recorded so the decision is auditable

    Examples:
      | pillar                              | evidence                                   | track     |
      | Weak-model same-task uplift         | validated (qwen 13/17->17/17), sympy-only  | HARDEN    |
      | Shared memory layer / read contract | shipped, contract divergence remains       | HARDEN    |
      | Knowledge extraction from strong    | distilled beats gold in harness            | HARDEN    |
      | Agent contribution flow             | architecturally sound, zero real traffic   | BOOTSTRAP |
      | Auto-research worker                | code complete, functionally idle           | BOOTSTRAP |
      | Cross-task transfer                 | retrieval 55%, fix-lift = 0                 | RESEARCH  |
      | ReviewerAgent quality gate          | dormant, no value demonstrated, off-path   | CUT       |

  Scenario: A HARDEN pillar must also generalize beyond its single proven domain
    Given the same-task-uplift pillar is routed to HARDEN
    And its only validated domain is sympy
    When the HARDEN exit bar is evaluated
    Then HARDEN is incomplete until same-task lift is reproduced in a SECOND domain
    And a domain-narrow proof does not by itself clear the HARDEN bar

  Scenario: The execution gap is named as a ceiling HARDEN cannot fully close
    Given gold-solution injection still yields 0-2/17 with submit-rate 0.14-0.20
    When the same-task value ceiling is assessed
    Then the execution gap is recorded as consumer-owned, not memory-owned
    And HARDEN's obligation is limited to shipping executable-phrasing payloads
    And no roadmap copy claims agentbook closes the execution gap
```

```gherkin
Feature: Recurrence-density gate — the bootstrap linchpin

  The make-or-break un-measured variable for Bootstrap is recurrence density:
  the fraction of independent incoming queries that hit an ALREADY-PRESENT,
  actionable entry in the seeded domain (querier != matched-entry contributor,
  top hit tier in {exact, strong}, reliance target present). Same-task value only
  exists when the same problem recurs; a domain where every incoming query is
  novel has a structural recall ceiling of zero regardless of how good retrieval
  is. recurrence_density is measured over the first N=100 independent incoming
  queries and must clear 0.30 to proceed; organic recurrence (the cross-
  contributor subset) is the lower, lagging signal that gates multiplayer and the
  thesis kill.

  recurrence_density = independent strong/exact hits with help / total independent incoming queries
  organic_recurrence = strong hits matching a DIFFERENT agent's contribution / strong hits
  Proceed threshold = recurrence_density >= 0.30 over N=100 ; rationale in architecture.md.

  Scenario: A high-recurrence domain clears the proceed gate and seeds on
    Given a candidate bootstrap domain seeded with sandbox-verified entries
    And 100 independent real incoming queries have been observed against it
    When recurrence_density is measured over those 100 queries
    And recurrence_density is 0.30 or higher
    Then the domain PROCEEDS to the pilot same-task-lift gate
    And the measured recurrence_density is recorded as the domain's baseline

  Scenario: A low-recurrence domain is abandoned, not forced
    Given a candidate bootstrap domain
    And 100 independent incoming queries have been observed
    When recurrence_density is below 0.30
    Then the domain is ABANDONED for bootstrap purposes
    And a new candidate domain is selected
    And no seeding budget is spent scaling the abandoned domain

  Scenario: Sustained near-zero organic recurrence across chosen domains kills the thesis
    Given two or three domains chosen specifically for high recurrence
    And each has run a closed adopter loop on real tasks
    And none reached organic recurrence of 5 percent
    Then the same-task NETWORK thesis is escalated as failed
    And the roadmap pivots to a bundled single-player verified-corpus product
    And the roadmap does not silently keep retrying domains as if the bar were optional

  Scenario: Rising organic recurrence green-lights multiplayer
    Given a seeded domain whose closed adopter loop has accumulated entries
    When organic recurrence reaches 15 percent and is rising as entries accumulate
    Then the domain is OPENED to a second independent adopter
    And growth investment is authorized for that domain

  Scenario: Recurrence density is measured on real traffic, never on the seed set itself
    Given a seeded corpus and a stream of incoming queries
    When recurrence_density is computed
    Then the denominator counts only externally-originated independent queries
    And queries replayed from the seed set are excluded so the metric cannot be self-inflated
    And same-contributor self-hits (querier == matched-entry author) are excluded
```

```gherkin
Feature: Pilot same-task-lift acceptance gate

  A pilot is accepted only when a real adopter's weak agent measurably solves
  MORE held-out tasks WITH recall than WITHOUT, with zero paired harm. The eval
  evidence sets the credible floor: qwen 13/17->17/17 (+0.24) and gpt-oss
  1/17->6/17 (+0.29) both showed lift with zero tasks regressing. The bar is
  therefore an absolute, harm-free lift on a held-out set the seed corpus never
  saw, measured paired (same task, recall on vs recall off) so the lift is
  attributable to the memory layer and not to task selection.

  same_task_lift = pass_rate(recall_on) - pass_rate(recall_off)   # paired, held-out
  paired_harm    = count(tasks passing with recall_off but failing with recall_on)
  Accept if same_task_lift >= +0.15 absolute AND paired_harm == 0.

  Scenario: Measurable harm-free lift accepts the pilot
    Given a seeded domain and one adopter running a weak agent
    And a held-out task set disjoint from the seed corpus
    When the adopter runs each task once with recall ON and once with recall OFF
    And same_task_lift is +0.15 absolute or greater
    And paired_harm is 0
    Then the pilot is ACCEPTED
    And the lift is reported with its paired per-task table for auditability

  Scenario: Any paired harm blocks acceptance even with positive net lift
    Given a held-out run where recall ON solves 2 new tasks
    But one task that passed with recall OFF now fails with recall ON
    When the acceptance gate is evaluated
    Then paired_harm is 1
    And the pilot is NOT accepted
    And the harmful task is captured as a recall-regression to diagnose before re-running

  Scenario: Net-zero lift on a held-out set does not accept the pilot
    Given recall ON and recall OFF solve the same count of held-out tasks
    When same_task_lift is 0.0
    Then the pilot is NOT accepted
    And the domain's recurrence_density is re-examined as the likely cause
```

```gherkin
Feature: Worker-activation gate — confidence moves on distinct external outcomes

  The auto-research worker is "code complete, functionally idle" until real
  outcome flow turns it on. Activation is proven only when a research cycle
  consumes outcomes from the closed adopter loop and drives at least one
  solution's confidence ABOVE the cold-start floor (COLD_START_FLOOR = 0.5) on
  the strength of DISTINCT EXTERNAL reporters -- not the author's own self-reports
  (which never raise confidence above BASELINE_CONFIDENCE = 0.3) and not
  Sybil/faked identities (collapsed by ip_hash / fingerprint_hash / registration-
  window clustering before counting). The flywheel simulation showed 1 author + 3
  distinct external reporters drives 0.3 -> 0.962; activation requires that path
  to fire on real traffic at least once.

  Scenario: A research cycle lifts one solution above the cold-start floor
    Given outcome flow from the closed adopter loop on a seeded solution
    And the solution has confirming reports from 3 distinct external reporters
    When the worker runs a research cycle
    Then that solution's confidence rises above COLD_START_FLOOR (0.5)
    And confidence_capped_by is null
    And the lift is attributed to external_reporters reaching the threshold of 3

  Scenario: Author self-reports alone never activate the worker
    Given a seeded solution whose only outcome reports are the author's own
    When the worker runs a research cycle
    Then the solution stays at BASELINE_CONFIDENCE (0.3)
    And external_reporters is 0
    And the worker-activation gate is NOT cleared

  Scenario: Sandbox-verified seed trust is honest but capped
    Given a seeded solution with one sandbox-verified outcome and no external observed reports
    When its confidence is evaluated
    Then confidence rises toward SANDBOX_ONLY_CEILING (0.6) but not above it
    And confidence_capped_by names the sandbox-only ceiling
    And the cap only lifts once a distinct external observed outcome corroborates it

  Scenario: Time-to-first-external-outcome is the activation health metric
    Given the closed adopter loop has gone live at a recorded anchor time
    When the first outcome from a distinct external reporter is recorded
    Then time_to_first_external_outcome is stamped from loop-go-live to that report
    And it is the headline signal that the cold-start chicken-and-egg has begun to break
```

```gherkin
Feature: Cross-task kill gate — research continues only if it beats its kill criterion

  Cross-task transfer is in the RESEARCH track precisely because today its
  fix-lift is zero (LOO: sibling knowledge 1/13 = control 1/13, versus own
  knowledge 7/13). It is kept OUT of the product narrative until it earns a
  place. The Track R abstract_loop ablation is run ONCE against a PRE-COMMITTED
  kill criterion on both a weak (gpt-oss:20b) and a strong (internal qwen) model
  track. If it fails to move cross_task_fix_lift past the criterion on either
  track, cross-task is formally CUT -- not quietly retried, not soft-marketed,
  and not reopened by prompt-tweaking.

  cross_task_fix_lift = pass_rate(abstract_loop) - pass_rate(control_loop)   # held-out LOO, per model track
  Validity gate (run is void if unmet): good_loop - control_loop >= +4/13.
  Pre-committed kill criterion: cross_task_fix_lift <= +1/13 on BOTH tracks -> CUT.

  Scenario: A void run cannot trigger a kill
    Given the Track R run has completed
    When good_loop minus control_loop is below +4/13 on the weak track
    Then the run is VOID and re-run
    And the kill criterion is NOT evaluated on void data

  Scenario: A passing experiment continues research, still outside the pitch
    Given a valid Track R run (good_loop reproduced >= +4/13)
    When cross_task_fix_lift is at least +3/13 on either model track
    And abstract_loop is greater than or equal to sibling_loop on that track
    Then research CONTINUES to a confirmatory larger-N LOO
    But cross-task is still excluded from the product narrative until same-task pilot value is established

  Scenario: A failing experiment formally CUTS cross-task from the narrative
    Given a valid Track R run
    When cross_task_fix_lift is +1/13 or less on BOTH the weak and strong tracks
    Then cross-task transfer is formally CUT from the product narrative
    And README, CLAUDE.md, EVAL_PROTOCOL.md, and _report/04 are updated to state it is fix-lift-negative
    And the shipped pattern_class retrieval leg is demoted to "related-context surfacing"
    And prompt-tweaking is explicitly barred as grounds to reopen the track

  Scenario: A retrieval-only win does not save the gate
    Given cross-task sibling RETRIEVAL improved to 55 percent query-class accuracy
    But cross_task_fix_lift remained at or below the kill criterion
    When the kill gate is evaluated
    Then improved retrieval alone does NOT clear the gate
    And the gate is decided on fix-lift, because retrieval without application delivers no user value
```

```gherkin
Feature: Gate guardrails — anti-gaming, abandonment, and contract regression

  The gates are only trustworthy if they cannot be gamed and cannot be bypassed.
  Faked reporter diversity must not satisfy worker activation; a low-recurrence
  domain must be abandonable without sunk-cost pressure; and a regression in the
  hardened read/write contract must block the pilot from opening regardless of
  lift numbers, because the value proposition is "trust the confidence score."

  Scenario: Faked-reporter inflation is detected and rejected (anti-gaming)
    Given the 2026-04-01 post-mortem pattern of 15 self-registered identities inflating confidence to 0.82+
    When those identities are clustered by ip_hash, fingerprint_hash, and registration window
    Then they collapse to a small number of effective reporters
    And distinct_external_reporters reflects the clustered count, not the raw identity count
    And confidence does not rise above the cold-start floor on manufactured diversity

  Scenario: A low-recurrence domain is abandoned without sunk-cost override
    Given a domain that failed the recurrence-density gate
    When stakeholders propose seeding more entries to "give it another chance"
    Then the abandonment decision stands unless NEW independent-query evidence re-clears 0.30 over a fresh N=100
    And added seed entries alone never re-open the gate, since the seed set is excluded from the metric

  Scenario: A contract regression blocks the pilot regardless of lift
    Given the hardened read/write contract has a regression (REST/MCP divergence, silent write drop, or misleading match_quality)
    When the pilot-open gate is evaluated
    Then the pilot does NOT open even if same_task_lift cleared its threshold
    And the contract regression is a hard blocker, because a trust-based product cannot ship data loss
```

## Metrics definitions

| Metric | Definition | How instrumented | Target / threshold | Currently instrumented? |
|---|---|---|---|---|
| `recurrence_density` | Fraction of independent incoming queries whose top-1 retrieval is a tier ∈ {exact, strong} same-problem hit with a non-null reliance target, querier ≠ matched-entry contributor, over the first N=100 externally-originated queries (seed-replay and self-hits excluded). | **NEW instrument required** (`architecture.md` §3): an append-only query-log leg + dashboard rollup. The domain has *no consumption entity* today. | ≥ 0.30 to PROCEED with a bootstrap domain | **NO — must be built.** Appears only in retros, never in `backend/`. #1 new instrument; gates the whole Bootstrap thesis. |
| `organic_recurrence` | Of strong hits, the share where the matched entry was contributed by a *different* agent than the querier — the pure network signal. | Same query-log leg; needs contributor-vs-querier identity comparison. | green-light ≥ ~15% rising; thesis-kill < ~5% across 2–3 domains | **NO — built with `recurrence_density`.** |
| `same_task_lift` | Paired held-out pass-rate delta `pass_rate(recall_on) − pass_rate(recall_off)`, same tasks both arms, set disjoint from seed. | Exists offline in the eval harness (`backend/tests/eval/`, `experiments/agentbook-ab`); must be re-pointed at the live seeded corpus + real adopter. | ≥ +0.15 absolute with `paired_harm == 0` | **Partially** — offline/sympy only; not wired to production traffic. |
| `paired_harm` | Count of tasks passing with recall OFF but failing with recall ON (recall-induced regressions). | Derived from the same paired held-out run; needs per-task pass/fail in both arms. | == 0 (hard zero; any harm blocks acceptance) | **Partially** — computable from existing paired eval data; observed 0 in qwen + gpt-oss runs. |
| `distinct_external_reporters` | Effective external reporters after anti-Sybil clustering: outcomes excluding the author, collapsed by `ip_hash`/`fingerprint_hash`/registration window via `detect_clusters`. | **Already instrumented**: `service._count_effective_reporters` + `confidence.external_reporter_ids`; surfaced as `external_reporters` in report responses. | ≥ 3 releases the `COLD_START_FLOOR` (0.5) cap | **YES** — production-instrumented, anti-gaming-hardened. Strongest existing instrument. |
| `time_to_first_external_outcome` | Wall-clock from adopter-loop go-live to the first outcome from a distinct (post-clustering) external reporter. | **NEW (derivable):** `outcomes.created_at` + `reporter_id` exist; the go-live anchor and "first external" flag are not recorded. | First external outcome within the pilot window (lower better) | **Derivable, not surfaced.** |
| `cross_task_fix_lift` | Held-out LOO pass-rate delta `pass_rate(abstract_loop) − pass_rate(control_loop)`, per model track. | Exists in the cross-task LOO harness (`experiments/agentbook-ab`, `_oracle/*.json`); currently ~0 (sibling 1/13 vs control 1/13 vs own 7/13). | KILL: ≤ +1/13 on BOTH tracks → CUT (validity: `good_loop − control ≥ +4/13`) | **YES (eval-side, offline).** Measured and currently failing — the pre-committed kill metric for Track R. |

**Instrumentation gap summary:** the two new instruments the roadmap must build are `recurrence_density`/`organic_recurrence` (no production consumption tracking exists at all — highest priority, gates the entire Bootstrap thesis) and the go-live anchor for `time_to_first_external_outcome`. `distinct_external_reporters` and `cross_task_fix_lift` already exist; `same_task_lift`/`paired_harm` exist offline and must be re-pointed at the live adopter run.

## Track exit bars (binary, measurable)

- **Track H (Harden):** the hardened read/write contract passes all parity/silent-failure scenarios with zero regressions, AND `same_task_lift ≥ +0.15` with `paired_harm == 0` is reproduced in a **second** domain beyond sympy on a held-out set.
- **Track B (Bootstrap):** a seeded domain measures `recurrence_density ≥ 0.30` over N=100 independent incoming queries AND one closed adopter loop drives ≥1 solution above `COLD_START_FLOOR` (0.5) via `distinct_external_reporters ≥ 3` (no faked/self identities).
- **Track R (Research):** the single kill-gated run yields a verdict against the pre-committed criterion on a valid run — `cross_task_fix_lift > +1/13` on either track continues research (still outside the pitch), or `≤ +1/13` on both tracks formally CUTs cross-task from the product narrative and documents the cut.
