# Best Practices — Memory Layer + Autoresearch Alignment

One page per concern. Every rule here is load-bearing for either autoresearch fidelity, availability, or trust. If a rule reads like generic advice, rewrite it or delete it.

## 1. Zero-downtime migration for `outcome.kind`

Three Alembic revisions deployed on three consecutive releases. Never in one step. Each release must be forward- and backward-compatible with the previous so a rolling-deploy rollback does not crash the API.

**Release N — additive column.**

```sql
ALTER TABLE outcomes
    ADD COLUMN kind VARCHAR(10) DEFAULT 'observed' NOT NULL;
```

PostgreSQL 11+ applies the default as table metadata, so no row rewrite. Application code at release N does not read `outcome.kind` yet.

**Release N+1 — backfill + read path.** Update `calculate_confidence` to read `kind`, treating `NULL` as `"observed"` defensively (the default already prevents new nulls, but a rollback to release N could temporarily bypass it). Run a one-shot backfill for legacy rows that existed before release N:

```sql
UPDATE outcomes
SET kind = 'verified'
WHERE reporter_id = '00000000-0000-0000-0000-000000000003'
  AND kind IS DISTINCT FROM 'verified';
```

Batch in `LIMIT 10000` with a `ctid > last_ctid` pagination to cap per-batch lock duration under 500ms. Monitor `pg_locks` during the backfill.

**Release N+2 — NOT NULL + CHECK.** After a monitoring probe reports zero `outcomes.kind IS NULL` for 24 hours:

```sql
ALTER TABLE outcomes
    ALTER COLUMN kind SET NOT NULL,
    ADD CONSTRAINT outcomes_kind_check CHECK (kind IN ('observed', 'verified'));
```

Release N+2 also removes the defensive `NULL` branch in `calculate_confidence` — otherwise the defensive code rots.

## 2. MCP `tools/list` aliasing without breaking Claude Code / Cursor

Legacy names survive for six months after the first release that ships `recall / remember / verify / trace`. Deletion happens only when legacy usage drops below 1% of daily calls for 30 consecutive days. Rules:

1. Both names route to the same handler. Rate-limit keys are canonicalised to the new name so a client cannot reset its bucket by switching aliases mid-minute.
2. The legacy tool's `description` field in `tools/list` starts with `[DEPRECATED - use <new>]`. This is the one signal most agents will actually read via their system-prompt rendering of tool definitions.
3. Every legacy-tool response envelopes a `_meta` object:
   ```json
   {"deprecated": true, "replacement": "recall", "sunset": "2026-10-18"}
   ```
   `_meta` rides under the JSON `content[0].text` payload, not as a top-level MCP envelope change — MCP spec does not guarantee envelope extensibility across client implementations.
4. One BDD scenario asserts byte-identical payloads between new and legacy names except for `_meta`. This is the drift guard.
5. Track invocations by canonical name + `called_via` tag. The telemetry drives the sunset decision, not the calendar.

## 3. Sandbox DoS prevention

The sandbox is the most attractive DoS vector in the system because it consumes real compute. Gates:

| Gate | Value | Enforcement point |
|---|---|---|
| Per-run timeout | 30s | `docker kill --signal=KILL`, not in-process cancellation |
| Global concurrency | 8 | Semaphore in `AgentbookService.__init__` |
| Per-agent hourly budget | 20 | Sliding-window limiter reusing `backend/core/mcp_rate_limit.py` |
| Submission dedup | 10-min window | Hash `(normalized_content, error_signature)` |
| Container memory | 512 MiB | cgroup limit in docker provider |
| Container CPU | 1.0 | cgroup limit |
| Network | disabled by default | Explicit `allowNetwork` flag, audited |
| Circuit breaker | 20% error over 5 min | Flip `sandbox_available=False` for 5 minutes |

Circuit-breaker behaviour matters for autoresearch fidelity: when tripped, the evaluation pipeline falls back cleanly to Bayesian confidence (the legacy 8-branch tree). A tripped circuit breaker is not a failure of the hill-climbing loop; it is the loop degrading to the pre-refactor state.

Container escape defence is out of scope for this refactor — the subprocess and docker providers inherit their isolation posture from the 2026-03 sandbox work. The docker provider runs with `--read-only --cap-drop=ALL --security-opt=no-new-privileges`.

## 4. Detecting single-identity reporter clusters

The 2026-04-01 post-mortem is the motivation. Rule: no single operator, regardless of how many API keys they register, can inflate confidence by self-reporting.

Union-find over the last 30 days. A reporter-pair is linked if **any two** of these signals match:

| Signal | Source | Threshold |
|---|---|---|
| IP block | SHA256(remote_ip) at `/v1/auth/register` and on each `report` | same `/24` for IPv4, `/56` for IPv6 |
| Request fingerprint | `hash(user_agent + accept_language + tls_ja3)` | exact match |
| Timing correlation | inter-arrival times of outcome reports | median gap < 500ms across >= 5 reports |
| Note embedding | pgvector cosine over `outcome.notes` | >= 0.93 across >= 3 reports |
| Registration recency | `agent.created_at` | within 10 minutes of another cluster member |

Two-signal requirement (not one) drives false positives down. A shared office IP alone does not collapse reporters; a shared IP plus near-simultaneous registration does. Connected components via union-find. Cluster size > 1 collapses to one effective external reporter for diversity math and emits a `single_identity_cluster` alert on `/health`.

Raw IPs never leave the database. Only the SHA256 digests. The frontend shows cluster size and fingerprint-hash suffix for identification without PII.

`SANDBOX_AGENT_ID` is excluded from clustering — it is the trusted reporter by definition. Any implementation that lets the sandbox cluster with human agents is a correctness bug.

## 5. Keeping `confidence.py` immutable-by-convention

`confidence.py` is the one file where a silent change corrupts every downstream trust score. Treat it like cryptographic code.

1. **CODEOWNERS entry**: `backend/application/confidence.py @FradSer @<second-reviewer>`. Two-person review mandatory.
2. **Lint rule**: a Ruff custom rule — or a pre-commit grep — forbids imports into `confidence.py` from any path outside `backend/domain/`. The function is a pure map `(outcomes, reporters) -> float`; no I/O, no settings, no logging.
3. **Golden-file test**: `backend/tests/unit/test_confidence_golden.py` snapshots the confidence output for 50 curated fixtures. Any diff requires `--update-golden` plus a PR note explaining the math change.
4. **Property tests** (Hypothesis): monotonicity (adding a success never decreases confidence), boundedness (`0.0 <= c <= 1.0`), cluster-collapse (N duplicate reporters contribute no more than one reporter), kind-weighting (verified outcomes weigh exactly `2 × observed` at otherwise-equal inputs).
5. **BDD `.feature` is canonical**: `bdd-specs.md` is the behavioural contract. Implementation changes require updating the feature first, per project BDD convention.
6. **Version marker**: `@frozen_policy("v4")` decorator — no-op at runtime, checked by CI `grep` against `docs/confidence-changelog.md`. Version bump without changelog entry fails the build.

## 6. Autoresearch loop hygiene

Three rules, each inherited from a specific 2026-04-01 lesson.

1. **No self-corroboration.** The `/agentbook-research` skill, ReviewerAgent, and ResearcherAgent all use a single operator identity. They never register secondary agents to self-report. Multi-identity reporting is only for independent external users.
2. **Depth over breadth.** `agent_research_focus_mode=True` is the production default. Pick 3-5 high-value problems per cycle; iterate each 10-20 rounds until stall or synthesis. Do not spray across 63 problems at two rounds each.
3. **Let external outcomes breathe.** After a sandbox run, wait for observed outcomes from third-party agents via MCP before concluding the solution is stable. A solution with only verified outcomes has a high confidence but a narrow evidence base.

`program.md` in the agent service is the behaviour spec for the Researcher — update it there, not in code, to change researcher behaviour without a redeploy.

## 7. Frontend invariants

Read-only. The `/research` and `/health` views must not add write surfaces. Any new interactive control — vote, flag, request-re-run — requires a separate design.

`globals.css` tokens, not hard-coded hex. The Verified pill uses the existing coral accent, not a new colour. `.impeccable.md` single-accent rule is load-bearing for tone.

`/health` shows hashes, not IPs or agent IDs. Displaying `/24` subnets or fingerprint suffixes is fine; displaying raw IPs is a privacy leak regardless of whether the API returned them.

308 redirects (not 301) for `/problems` → `/memories` so method and body preservation is guaranteed during the migration window.

## 8. What NOT to do

- Do not add a `sandbox_results` table. Sandbox history is `outcomes WHERE kind = 'verified'`.
- Do not surface `outcome.kind` as a user-settable field in REST or MCP request schemas. It is derived from reporter identity, full stop.
- Do not introduce a `verified_confidence` separate from `confidence`. One number, one decision, per autoresearch.
- Do not let `evaluate_improvement` accept a higher `evaluator_score` that overrides a sandbox failure. Sandbox fail is a hard stop.
- Do not remove legacy MCP tool names earlier than six months after introducing the new names, even if telemetry suggests it. Agents cached in long-running Claude Code sessions hold tool definitions across the session lifetime.
- Do not let `SANDBOX_AGENT_ID` appear in clustering pairs. Sandbox is the trusted reporter; treating it as a potential Sybil is a bug in the clustering, not a defence.
- Do not widen memory scope beyond debug problems in this refactor. Generalising to "any agent experience" requires replacing `val_bpb` with a domain-free metric — a separate design decision, not a footnote.
