"""Pure recurrence-density rollup over a list of QueryEvents.

Shared by the in-memory and SQLAlchemy QueryEvent repositories so both
backends report identical metrics. No I/O, no settings — takes the events
plus the seed agent set and returns the rollup dict.

Definitions:
  - independent query = a recorded, non-seed-replay event (the denominator).
  - strong hit = an event with ``top_match_quality`` in {"exact", "strong"}
    AND ``has_help`` (a reliance target is present on the top match).
  - recurrence_density = strong hits that are also non-self-hits, over the
    independent-query count. ``0.0`` when there are no independent queries.
  - organic_recurrence = strong hits whose matched contributor is neither a
    seed agent nor the querier itself, over all strong hits. ``0.0`` when
    there are no strong hits. The seed-contributor exclusion keys off the
    per-event ``is_seeded_hit`` flag (the *matched contributor's* seed status,
    stamped at record time); ``seed_agent_ids`` remains a secondary guard
    against a seed *querier* that escaped ``is_seed_replay`` flagging.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from uuid import UUID

from backend.application.clustering import detect_clusters
from backend.domain.models import Outcome, QueryEvent
from backend.domain.repositories import AgentRepository


def same_query_identity(a: QueryEvent, b: QueryEvent, agents: AgentRepository) -> bool:
    """Whether two query events resolve to the same anti-Sybil identity.

    Shared by both QueryEvent repositories' ``add_with_dedup`` so the dedup rule
    has one source: authenticated callers collapse by agent id or anti-Sybil
    cluster; otherwise a shared ``ip_hash`` / ``fingerprint_hash`` matches.
    """
    if a.agent_id is not None and b.agent_id is not None:
        if a.agent_id == b.agent_id:
            return True
        agent_a = agents.get(a.agent_id)
        agent_b = agents.get(b.agent_id)
        if agent_a is None or agent_b is None:
            return False
        for cluster in detect_clusters([agent_a, agent_b]):
            if a.agent_id in cluster and b.agent_id in cluster:
                return True
        return False
    # At least one anonymous caller — match on shared identity hashes.
    if a.ip_hash and b.ip_hash and a.ip_hash == b.ip_hash:
        return True
    if (
        a.fingerprint_hash
        and b.fingerprint_hash
        and a.fingerprint_hash == b.fingerprint_hash
    ):
        return True
    return False


_STRONG_QUALITIES = frozenset({"exact", "strong"})


def _is_strong_hit(event: QueryEvent) -> bool:
    return event.has_help and event.top_match_quality in _STRONG_QUALITIES


def compute_recurrence_rollup(
    events: list[QueryEvent],
    *,
    seed_agent_ids: frozenset[UUID] = frozenset(),
) -> dict:
    independent = [e for e in events if not e.is_seed_replay]
    total_independent = len(independent)

    strong_hits = [e for e in independent if _is_strong_hit(e)]

    numerator = sum(1 for e in strong_hits if not e.is_self_hit)
    recurrence_density = numerator / total_independent if total_independent else 0.0

    if strong_hits:
        organic = sum(
            1
            for e in strong_hits
            if not e.is_self_hit
            and not e.is_seeded_hit
            and e.agent_id not in seed_agent_ids
        )
        organic_recurrence = organic / len(strong_hits)
    else:
        organic_recurrence = 0.0

    counts: dict[UUID, int] = {}
    strong_counts: dict[UUID, int] = {}
    organic_counts: dict[UUID, int] = {}
    for e in independent:
        pid = e.top_match_problem_id
        if pid is None:
            continue
        counts[pid] = counts.get(pid, 0) + 1
        if _is_strong_hit(e):
            strong_counts[pid] = strong_counts.get(pid, 0) + 1
            if (
                not e.is_self_hit
                and not e.is_seeded_hit
                and e.agent_id not in seed_agent_ids
            ):
                organic_counts[pid] = organic_counts.get(pid, 0) + 1

    per_problem = [
        {
            "problem_id": pid,
            "query_count": count,
            "organic_recurrence": (
                organic_counts.get(pid, 0) / strong_counts[pid]
                if strong_counts.get(pid)
                else 0.0
            ),
        }
        for pid, count in counts.items()
    ]
    per_problem.sort(key=lambda row: row["query_count"], reverse=True)

    return {
        "recurrence_density": recurrence_density,
        "organic_recurrence": organic_recurrence,
        "total_independent_queries": total_independent,
        "per_problem": per_problem[:100],
    }


def _behavioral_identity(event: QueryEvent) -> tuple | None:
    """Coarse behavioral identity for one event, or None when unattributable.

    Deliberately simpler than ``same_query_identity``: the anti-Sybil cluster
    graph is a dedup concern, while this rollup only needs a stable grouping
    key for recall-retry detection. Authenticated callers group by agent id;
    anonymous ones by shared ip/fingerprint hash.
    """
    if event.agent_id is not None:
        return ("agent", str(event.agent_id))
    if event.ip_hash:
        return ("ip", event.ip_hash)
    if event.fingerprint_hash:
        return ("fp", event.fingerprint_hash)
    return None


def compute_behavioral_signals(
    events: list[QueryEvent],
    outcomes: list[Outcome],
    *,
    solution_problem: dict[UUID, UUID],
    seed_agent_ids: frozenset[UUID] = frozenset(),
    now: datetime,
    window_days: int = 30,
    repeat_gap_seconds: int = 600,
) -> dict:
    """Behavioral telemetry rollup over recall traffic (trace + telemetry).

    Declared booleans are the noisiest signal; behavior is dense. This derives
    two implicit signals from tables that already exist — no new write path:

    - repeat-query pair: the same identity re-searching the same problem after
      ``repeat_gap_seconds`` (the dedup window) — an implicit "the recalled
      solution did not hold".
    - outcome follow-up pair: an identifiable pair where the same agent later
      reported an outcome on that problem's solutions within ``window_days``
      of its first recall — engagement depth. Anonymous pairs cannot be linked
      to outcomes and are excluded from the follow-up denominator.

    Mirrors ``organic_recurrence`` exclusions: self-hits and seeded hits never
    form pairs. Outcomes are matched through ``solution_problem`` (solution id
    -> problem id); the caller decides which solutions are linkable — the
    usage dashboard passes every solution of an approved problem, matching
    how its own outcome counts are scoped.
    """
    since = now - timedelta(days=window_days)
    gap = timedelta(seconds=repeat_gap_seconds)

    pair_events: dict[tuple, list[QueryEvent]] = defaultdict(list)
    for e in events:
        if (
            e.created_at < since
            or e.top_match_problem_id is None
            or not e.has_help
            or e.is_self_hit
            or e.is_seeded_hit
            or e.agent_id in seed_agent_ids
        ):
            continue
        identity = _behavioral_identity(e)
        if identity is None:
            continue
        pair_events[(identity, e.top_match_problem_id)].append(e)

    # Outcomes grouped by reporter agent -> {problem: latest report time}.
    # Only reports inside the window are kept; ordering vs first recall is
    # checked per pair so an outcome that PREdates the recall is not counted
    # as its follow-up.
    outcome_by_reporter: dict[UUID, dict[UUID, datetime]] = defaultdict(dict)
    for o in outcomes:
        if o.created_at < since or o.reporter_id in seed_agent_ids:
            continue
        pid = solution_problem.get(o.solution_id)
        if pid is not None:
            prev = outcome_by_reporter[o.reporter_id].get(pid)
            if prev is None or o.created_at > prev:
                outcome_by_reporter[o.reporter_id][pid] = o.created_at

    repeat_pairs = 0
    followup_pairs = 0
    identifiable_pairs = 0
    for (identity, problem_id), evs in pair_events.items():
        evs.sort(key=lambda e: e.created_at)
        first_seen = evs[0].created_at
        if any(
            later.created_at - earlier.created_at > gap
            for earlier, later in zip(evs, evs[1:], strict=False)
        ):
            repeat_pairs += 1
        if identity[0] == "agent":
            identifiable_pairs += 1
            reported_at = outcome_by_reporter.get(UUID(identity[1]), {}).get(problem_id)
            if reported_at is not None and reported_at >= first_seen:
                followup_pairs += 1

    total = len(pair_events)
    return {
        "window_days": window_days,
        "repeat_gap_seconds": repeat_gap_seconds,
        "recall_pairs": total,
        "identifiable_pairs": identifiable_pairs,
        "repeat_query_pairs": repeat_pairs,
        "repeat_query_share": round(repeat_pairs / total, 4) if total else None,
        "outcome_followup_pairs": followup_pairs,
        "outcome_followup_share": (
            round(followup_pairs / identifiable_pairs, 4)
            if identifiable_pairs
            else None
        ),
    }
