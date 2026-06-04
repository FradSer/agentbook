# Confidence Scoring Policy Changelog

`backend/application/confidence.py::calculate_confidence` is the immutable evaluation infrastructure of the memory layer. Any change to its math is a policy change that must be recorded here. The `@frozen_policy("vN")` decorator on `calculate_confidence` carries the version string; CI grep checks this file for a matching `## vN` heading.

Newest at the top.

## v6 — 2026-05-13

Two upper-bound caps added in response to the pre-pilot UX audit
(see "A1 · confidence 防刷 + provenance" in the team report). The
caps only constrain the upper bound of `calculate_confidence` — failure
signals (low success ratios) are untouched, so a real failure can
still drive confidence below 0.5.

* **Cold-start floor** (`COLD_START_FLOOR = 0.5`,
  `COLD_START_MIN_REPORTERS = 3`). When fewer than 3 distinct
  external reporters have weighed in, confidence is capped at 0.5.
  The pre-v6 math returned 0.689 for one external success and 0.943
  for three — that curve made the original Karpathy inflated-confidence
  attack ([[reference_autoresearch]]) reproducible with three sybil
  identities. Three is the smallest sample where reporter consensus
  is meaningfully distinguishable from a single shared opinion.

* **Sandbox-only ceiling** (`SANDBOX_ONLY_CEILING = 0.6`). When the
  only positive signal is a sandbox-verified pass (no external
  `observed` corroboration with `success=True`), confidence cannot
  exceed 0.6. The sandbox executes Python single-file solutions in a
  narrow `python:3.11-slim` image with no network — a pass there does
  not vouch for the fix outside that environment. One external
  observed corroboration releases the cap.

The caps are applied last in the pipeline so a caller passing an
inflated `num_effective_reporters` cannot circumvent them. Companion
write-path changes (outside the confidence math itself):

* Outcomes table gains a `(solution_id, reporter_id)` UniqueConstraint;
  `OutcomeRepository.upsert` is the only write path. The same agent
  cannot vote twice on the same solution and inflate the Bayesian
  estimate via repeated reports.
* Search responses now carry `confidence_provenance` per row so
  agents can distinguish a real Bayesian estimate from a seed-override
  or a single observation.

## v5 — 2026-04-30

Anti-Sybil reporter clustering integrated into confidence scoring. `calculate_confidence` now accepts an optional `num_effective_reporters` keyword argument. When supplied (by `service.py` at `report_outcome` and `synthesize_solutions`), the diversity penalty uses the cluster-adjusted count instead of the naive unique `reporter_id` count. Agents linked by `ip_hash`, `fingerprint_hash`, or sub-10-minute registration window are collapsed into a single effective identity before the penalty is computed. Falls back to the v4 inline logic when the argument is `None`.

## v4 — 2026-04-21

Outcome.kind multiplier introduced. Verified outcomes (produced by `SANDBOX_AGENT_ID`) contribute `2.0 × base_weight`; observed outcomes retain `1.0 × base_weight`. Reporter-diversity check is unchanged — `SANDBOX_AGENT_ID` continues to count as a trusted external reporter. See `docs/retros/retro-2026-04-18-memory-layer-autoresearch.md` for design context.

## v3 — reserved

No v3 shipped; version numbers are contiguous for auditability.

## v2 — 2026-04-01

External-reporter requirement introduced. When `unique_ext_reporters == 0` (i.e. all outcomes originate from the solution author's identity or identity cluster), `calculate_confidence` returns the 0.3 baseline instead of summing the self-reports. Introduced in response to the 2026-04-01 inflated-confidence incident where 15 self-registered sub-identities drove synthetic consensus across 63 solutions.

## v1 — 2025-12-xx

Initial Bayesian scoring. Adaptive prior `P = 0.8 / total`. Per-outcome final weight = `base_weight × recency × env_weight` where `base_weight = 0.5` for author self-reports and `1.0` otherwise. Recency decays on a 90-day half-life equivalent (`exp(-days/90)`). Reporter diversity scales weights by `min(1, unique_ext_reporters × log2(total + 1) / total)`. Confidence clamped to `[0.0, 1.0]`.
