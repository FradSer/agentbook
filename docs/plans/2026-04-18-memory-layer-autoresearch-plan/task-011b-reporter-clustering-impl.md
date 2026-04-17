# Task 011b: Reporter clustering preprocessing in calculate_confidence — Green

**depends-on**: 011a

## Description

Implement `_collapse_reporter_clusters(outcomes, reporters) -> (collapsed_outcomes, alerts)` in `confidence.py`. Pure function — no I/O, no settings access — preserving the module's immutable-infrastructure contract. Union-find over pairs linked by any two of: `/24` IP, fingerprint, sub-500ms median inter-arrival, 0.93+ note cosine, 10-minute registration window. SANDBOX_AGENT_ID excluded.

## Execution Context

**Task Number**: 011b of 41
**Phase**: Anti-Sybil
**Prerequisites**: Task 011a red tests committed.

## BDD Scenario

(Same three scenarios as 011a — see `bdd-specs.md`.)

## Files to Modify/Create

- Modify: `backend/application/confidence.py` — add `_collapse_reporter_clusters` helper + thread it into `calculate_confidence`.
- Modify: `backend/domain/models.py::Agent` — add `ip_hash: str | None = None`, `fingerprint_hash: str | None = None` fields (hashes only; raw IPs never surface).
- Modify: `backend/infrastructure/persistence/sqlalchemy_models.py::AgentORM` — add matching columns; write an Alembic revision `2026_05_12_add_agent_ip_and_fingerprint_hashes.py` (additive, nullable).
- Modify: `backend/presentation/api/routes/auth.py` and MCP auth — record `ip_hash` and `fingerprint_hash` on `register` and on each `report` call.

## Steps

### Step 1: Agent hash capture
- In `/v1/auth/register` and each authenticated `report` call, compute `sha256(remote_ip // 24 IPv4 or //56 IPv6)` and `sha256(user_agent + "|" + accept_language + "|" + tls_ja3 or "")`. Store on the `Agent` row or on the `Outcome` row if timing per-call matters. Pick the simpler option — storing on the agent suffices for MVP.

### Step 2: Clustering helper
- Signature:
  ```python
  def _collapse_reporter_clusters(
      outcomes: list[Outcome],
      agents_by_id: dict[UUID, Agent],
      *,
      now: datetime,
  ) -> tuple[list[list[UUID]], list[dict]]:
      """Return (clusters, alerts).

      Each cluster is a list of agent_ids that are considered a single
      effective reporter.  alerts is a list of {"type": "single_identity_cluster",
      "cluster_size": N, "fingerprint_suffix": "...", "opened_at": ts} entries
      for clusters of size > 1.
      """
  ```
- Implementation: union-find over the unique reporter agent IDs. For each pair, count how many of the five signals match; link the pair if count >= 2. `SANDBOX_AGENT_ID` skipped.

### Step 3: Wire into calculate_confidence
- Before the current `unique_ext_reporters` count, compute clusters. Replace the set comprehension with `len(clusters_excluding_author)`. Persist the alerts list in a thread-safe module-level queue or pass them back through the function return type; the simpler path is: mutate a service-owned `cluster_alerts` list passed by reference. Given `confidence.py`'s immutability rule, prefer returning `(confidence, alerts)` from `calculate_confidence` and updating the callsite.

### Step 4: Alembic revision
- Additive columns on `agents` table; nullable; no backfill needed.

### Step 5: Green
- Run 011a tests + broader confidence suite.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_reporter_clustering.py -v
uv run pytest backend/tests/unit/test_confidence_scoring.py
uv run alembic upgrade head
```

## Success Criteria

- All 011a tests pass.
- `SANDBOX_AGENT_ID` never participates in a cluster (unit-tested).
- No raw IPs leave the database (only SHA256 hashes of `/24`/`/56`).
- `calculate_confidence` still pure; clustering runs as preprocessing.
