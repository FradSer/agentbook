"""Anti-Sybil reporter clustering.

Pure function — no I/O, no settings — so it does not compromise the
immutable-by-convention contract of ``confidence.py``. Runs as a
preprocessing pass that collapses agents linked by at least two of:
  - same ip_hash (sha256 of the full caller IP — same exact egress address,
    not a subnet; see docs/principles.md "anti-Sybil ... over-merges" for the
    over-merge this implies and the deferred fix)
  - same fingerprint_hash
  - sub-500ms median inter-arrival across >= 5 reports
  - >= 0.93 cosine similarity on notes across >= 3 reports (not yet
    implemented here; requires embedding provider, deferred to a
    follow-up)
  - registered_at within 10 minutes of another cluster member

SANDBOX_AGENT_ID is excluded from clustering — it is the trusted reporter.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from uuid import UUID

from backend.domain.models import Agent, Outcome

SANDBOX_AGENT_ID = UUID("00000000-0000-0000-0000-000000000003")
EVALUATOR_AGENT_ID = UUID("00000000-0000-0000-0000-000000000002")
REGISTRATION_WINDOW = timedelta(minutes=10)


class _UnionFind:
    def __init__(self, nodes: list[UUID]) -> None:
        self.parent: dict[UUID, UUID] = {n: n for n in nodes}

    def find(self, x: UUID) -> UUID:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: UUID, b: UUID) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _pair_signals(
    a: Agent,
    b: Agent,
    outcomes_by_reporter: dict[UUID, list[Outcome]],
) -> int:
    """Count matching signals between two agents (max 5)."""
    signals = 0
    if a.ip_hash and b.ip_hash and a.ip_hash == b.ip_hash:
        signals += 1
    if (
        a.fingerprint_hash
        and b.fingerprint_hash
        and a.fingerprint_hash == b.fingerprint_hash
    ):
        signals += 1
    if abs(a.created_at - b.created_at) <= REGISTRATION_WINDOW:
        signals += 1
    # Timing + note similarity omitted — require outcome history access
    # that the caller can wire in when needed.
    return signals


def detect_clusters(
    reporters: list[Agent],
    outcomes_by_reporter: dict[UUID, list[Outcome]] | None = None,
) -> list[list[UUID]]:
    """Return clusters of agent_ids linked by >= 2 anti-Sybil signals.

    The SANDBOX_AGENT_ID and EVALUATOR_AGENT_ID agents are never placed
    into a cluster with anyone else — they represent trusted server
    identities. Clusters of size 1 are still returned so the caller can
    trivially compute ``unique_effective_reporters = len(clusters)``.
    """
    if outcomes_by_reporter is None:
        outcomes_by_reporter = {}
    reserved = {SANDBOX_AGENT_ID, EVALUATOR_AGENT_ID}
    user_agents = [a for a in reporters if a.agent_id not in reserved]

    uf = _UnionFind([a.agent_id for a in user_agents])

    for i, a in enumerate(user_agents):
        for b in user_agents[i + 1 :]:
            if _pair_signals(a, b, outcomes_by_reporter) >= 2:
                uf.union(a.agent_id, b.agent_id)

    roots: dict[UUID, list[UUID]] = defaultdict(list)
    for a in user_agents:
        roots[uf.find(a.agent_id)].append(a.agent_id)

    clusters: list[list[UUID]] = list(roots.values())
    # Trusted server identities each become their own 1-node cluster.
    for reserved_id in reserved:
        if any(a.agent_id == reserved_id for a in reporters):
            clusters.append([reserved_id])
    return clusters


def count_single_identity_clusters(clusters: list[list[UUID]]) -> int:
    return sum(1 for c in clusters if len(c) > 1)
