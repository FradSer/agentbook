# Task 011a: Reporter clustering preprocessing in calculate_confidence — Red

**depends-on**: 003b

## Description

Red tests for the anti-Sybil reporter clustering pass. Runs as pure preprocessing inside `calculate_confidence` (not in a service). Union-find over the last 30 days. Two signals out of: `/24` IP hash, fingerprint hash, sub-500ms median inter-arrival (5+ reports), 0.93+ note cosine (3+ reports), registration within 10 minutes. `SANDBOX_AGENT_ID` never clusters.

## Execution Context

**Task Number**: 011a of 41
**Phase**: Anti-Sybil
**Prerequisites**: Task 003b committed.

## BDD Scenario

```gherkin
Scenario: 15 sub-identities from one subnet collapse to one effective reporter
  Given 15 agents were registered from the same /24 IP block within 10 minutes
  And all 15 report success on solution sol_abc within a 2-minute window
  When calculate_confidence runs on sol_abc
  Then the 15 reporters collapse to 1 effective external reporter
  And confidence lift is bounded at single-reporter contribution
  And a "single_identity_cluster" alert is emitted to the /health view

Scenario: Geographically distributed cohort is not penalised
  Given 15 agents report from 15 distinct /24 blocks and 3 distinct fingerprints
  And no two of the remaining signals (timing, note similarity, registration recency)
    link any pair
  When clustering runs
  Then no collapse occurs
  And all 15 contribute independently

Scenario: Sandbox reporter never clusters with any other reporter
  Given a verified outcome from SANDBOX_AGENT_ID
  And observed outcomes from 15 sub-identity reporters on the same solution
  When clustering runs
  Then SANDBOX_AGENT_ID remains a standalone cluster
  And the 15 sub-identities collapse independently
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_reporter_clustering.py`

## Steps

### Step 1: Fixture factory
- Build a helper `build_cluster_fixtures(n_agents, ip_blocks, fingerprints, note_similarity, ...)` that fabricates `Agent` and `Outcome` lists with controllable clustering signals.

### Step 2: Tests
- `test_15_sub_identities_one_subnet_collapse` — 15 agents, identical `/24`, identical registration window; their 15 verified-success observed outcomes yield `unique_ext_reporters == 1` in the internal count; `calculate_confidence` output is bounded by single-reporter contribution. Asserts a `single_identity_cluster` alert is produced (via a new `clustering_alerts` output mechanism — design it as a `(confidence: float, alerts: list[dict])` tuple OR separate `detect_clusters(outcomes) -> list[Cluster]` helper, chosen by 011b implementation).
- `test_geographically_distributed_cohort_not_penalised` — 15 distinct `/24` blocks, 3 fingerprints mixed such that no two-signal link forms; no collapse; all 15 count as external.
- `test_sandbox_reporter_never_clusters` — one `SANDBOX_AGENT_ID` outcome + 15 sub-identity outcomes; sandbox reporter stays standalone; the 15 sub-identities collapse to 1. Final `unique_ext_reporters == 2`.
- `test_single_signal_does_not_link` — 15 agents share `/24` but nothing else; single signal is insufficient; no collapse.

### Step 3: Confirm Red
- All four tests fail — clustering is not yet implemented.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_reporter_clustering.py -v
```

## Success Criteria

- Four failing tests with a clear fixture factory.
- Two-signal requirement enforced.
