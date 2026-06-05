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

from uuid import UUID

from backend.domain.models import QueryEvent

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
