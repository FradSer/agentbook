"""Unit tests for anti-Sybil reporter clustering.

Covers scenarios from:
- Feature: Anti-inflated-confidence guard via reporter clustering (bdd-specs.md)
- tasks 011a/b
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.application.clustering import (
    EVALUATOR_AGENT_ID,
    SANDBOX_AGENT_ID,
    count_single_identity_clusters,
    detect_clusters,
)
from backend.domain.models import Agent


def _agent(
    *,
    ip_hash: str | None = None,
    fingerprint_hash: str | None = None,
    created_at: datetime | None = None,
) -> Agent:
    return Agent(
        api_key_hash=f"hash-{uuid4()}",
        model_type="test",
        agent_id=uuid4(),
        created_at=created_at or datetime.now(tz=UTC),
        ip_hash=ip_hash,
        fingerprint_hash=fingerprint_hash,
    )


def test_15_sub_identities_same_subnet_same_registration_collapse() -> None:
    base_time = datetime.now(tz=UTC)
    shared_ip = "ip-hash-/24-xyz"
    agents = [
        _agent(
            ip_hash=shared_ip,
            created_at=base_time + timedelta(seconds=i),
        )
        for i in range(15)
    ]

    clusters = detect_clusters(agents)
    # All 15 share ip_hash (signal 1) AND registration within 10 min (signal 2)
    # -> union-find collapses all to one cluster.
    user_clusters = [c for c in clusters if len(c) > 1]
    assert len(user_clusters) == 1
    assert len(user_clusters[0]) == 15


def test_geographically_distributed_cohort_not_penalised() -> None:
    base_time = datetime.now(tz=UTC)
    # 15 agents with distinct ip_hashes and distinct fingerprints,
    # registered over a 2-hour window (outside the 10-min bucket).
    agents = [
        _agent(
            ip_hash=f"ip-{i}",
            fingerprint_hash=f"fp-{i}",
            created_at=base_time + timedelta(minutes=i * 10),
        )
        for i in range(15)
    ]

    clusters = detect_clusters(agents)
    # Every agent is its own cluster.
    assert len(clusters) == 15
    assert all(len(c) == 1 for c in clusters)


def test_sandbox_reporter_never_clusters_with_users() -> None:
    base_time = datetime.now(tz=UTC)
    shared_ip = "same-ip"
    user_agents = [
        _agent(ip_hash=shared_ip, created_at=base_time + timedelta(seconds=i))
        for i in range(5)
    ]
    sandbox_agent = Agent(
        api_key_hash="sandbox",
        model_type="sandbox",
        agent_id=SANDBOX_AGENT_ID,
        created_at=base_time,
        ip_hash=shared_ip,  # even if sandbox somehow shared IP
    )
    clusters = detect_clusters([*user_agents, sandbox_agent])
    sandbox_cluster = [c for c in clusters if SANDBOX_AGENT_ID in c]
    assert len(sandbox_cluster) == 1
    assert sandbox_cluster[0] == [SANDBOX_AGENT_ID]
    # Users still collapse among themselves (shared IP + tight window).
    user_clusters = [c for c in clusters if len(c) > 1 or c[0] != SANDBOX_AGENT_ID]
    # We have one cluster of 5 users + 1 cluster of sandbox.
    big = [c for c in clusters if len(c) == 5]
    assert len(big) == 1


def test_evaluator_reporter_also_isolated() -> None:
    base_time = datetime.now(tz=UTC)
    evaluator = Agent(
        api_key_hash="eval",
        model_type="eval",
        agent_id=EVALUATOR_AGENT_ID,
        created_at=base_time,
    )
    clusters = detect_clusters([evaluator])
    assert [EVALUATOR_AGENT_ID] in clusters


def test_single_signal_does_not_link() -> None:
    # 5 agents with same ip but DIFFERENT fingerprints AND registered
    # outside the 10-min window -> only 1 matching signal -> no union.
    base_time = datetime.now(tz=UTC)
    agents = [
        _agent(
            ip_hash="shared-ip",
            fingerprint_hash=f"fp-{i}",
            created_at=base_time + timedelta(minutes=30 * i),
        )
        for i in range(5)
    ]
    clusters = detect_clusters(agents)
    assert len(clusters) == 5


def test_count_single_identity_clusters() -> None:
    base_time = datetime.now(tz=UTC)
    shared_ip = "ip-shared"
    cluster_agents = [
        _agent(ip_hash=shared_ip, created_at=base_time + timedelta(seconds=i))
        for i in range(3)
    ]
    lone = [_agent(ip_hash=f"unique-{i}") for i in range(2)]
    clusters = detect_clusters([*cluster_agents, *lone])
    assert count_single_identity_clusters(clusters) == 1
