"""Verifies features/behavioral-telemetry.feature.

Server-side behavioral telemetry: repeat-query pairs (implicit "the recalled
solution did not hold") and outcome follow-up pairs (engagement depth),
aggregated into ``get_usage_dashboard``'s new ``behavioral_signals`` section.
No new write hot path — everything derives from query_events + outcomes.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from backend.application._recurrence import compute_behavioral_signals
from backend.application.service import AgentbookService
from backend.domain.models import Agent, Outcome, QueryEvent, utc_now
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryQueryEventRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)

ZEROED = {
    "window_days": 30,
    "repeat_gap_seconds": 600,
    "recall_pairs": 0,
    "identifiable_pairs": 0,
    "repeat_query_pairs": 0,
    "repeat_query_share": None,
    "outcome_followup_pairs": 0,
    "outcome_followup_share": None,
}


def _service_with_query_log() -> tuple[AgentbookService, UUID]:
    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(Agent(api_key_hash="h", model_type="test", agent_id=author_id))
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
        query_events=InMemoryQueryEventRepository(),
    )
    return service, author_id


def _event(
    *,
    agent_id: UUID | None = None,
    ip_hash: str | None = None,
    fingerprint_hash: str | None = None,
    problem_id: UUID | None,
    created_at: datetime | None = None,
    has_help: bool = True,
    is_self_hit: bool = False,
    is_seeded_hit: bool = False,
) -> QueryEvent:
    return QueryEvent(
        query_text="some query",
        agent_id=agent_id,
        ip_hash=ip_hash,
        fingerprint_hash=fingerprint_hash,
        top_match_problem_id=problem_id,
        top_match_quality="strong" if has_help else None,
        has_help=has_help,
        is_self_hit=is_self_hit,
        is_seed_replay=False,
        is_seeded_hit=is_seeded_hit,
        created_at=created_at or utc_now(),
    )


def _seed_problem_with_solution(
    service: AgentbookService, author_id: UUID
) -> tuple[UUID, UUID]:
    problem = service.create_problem(
        author_id=author_id,
        description="Docker socket permission denied on fresh install",
    )
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Add the user to the docker group and restart the session.",
    )
    return problem.problem_id, solution.solution_id


def _signals(service: AgentbookService) -> dict:
    return service.get_usage_dashboard()["behavioral_signals"]


# --- Pure-function unit coverage --------------------------------------------


def test_empty_traffic_yields_zeroed_section() -> None:
    rollup = compute_behavioral_signals(
        [], [], solution_problem={}, seed_agent_ids=frozenset(), now=utc_now()
    )
    assert rollup["recall_pairs"] == 0
    assert rollup["repeat_query_share"] is None


def test_repeat_after_gap_counts_as_repeat_pair() -> None:
    now = utc_now()
    pid = uuid4()
    agent = uuid4()
    events = [
        _event(agent_id=agent, problem_id=pid, created_at=now - timedelta(hours=2)),
        _event(agent_id=agent, problem_id=pid, created_at=now - timedelta(hours=0)),
    ]
    rollup = compute_behavioral_signals(
        events,
        [],
        solution_problem={},
        seed_agent_ids=frozenset({uuid4()}),
        now=now,
    )
    assert rollup["recall_pairs"] == 1
    assert rollup["repeat_query_pairs"] == 1
    assert rollup["repeat_query_share"] == 1.0


def test_rapid_duplicates_inside_dedup_window_are_noise() -> None:
    now = utc_now()
    pid = uuid4()
    agent = uuid4()
    events = [
        _event(agent_id=agent, problem_id=pid, created_at=now - timedelta(seconds=60)),
        _event(agent_id=agent, problem_id=pid, created_at=now),
    ]
    rollup = compute_behavioral_signals(
        events, [], solution_problem={}, seed_agent_ids=frozenset(), now=now
    )
    assert rollup["recall_pairs"] == 1
    assert rollup["repeat_query_pairs"] == 0


def test_seeded_and_self_hits_excluded_from_pairs() -> None:
    now = utc_now()
    pid = uuid4()
    seed_agent = uuid4()
    author = uuid4()
    gap = timedelta(hours=2)
    events = [
        _event(
            agent_id=seed_agent,
            problem_id=pid,
            created_at=now - gap * 2,
            is_seeded_hit=True,
        ),
        _event(
            agent_id=seed_agent,
            problem_id=pid,
            created_at=now - gap,
            is_seeded_hit=True,
        ),
        _event(
            agent_id=author,
            problem_id=pid,
            created_at=now - gap * 2,
            is_self_hit=True,
        ),
        _event(
            agent_id=author,
            problem_id=pid,
            created_at=now - gap,
            is_self_hit=True,
        ),
    ]
    rollup = compute_behavioral_signals(
        events, [], solution_problem={}, seed_agent_ids=frozenset({seed_agent}), now=now
    )
    assert rollup["recall_pairs"] == 0


def test_outcome_by_same_agent_counts_as_followup() -> None:
    now = utc_now()
    pid = uuid4()
    sid = uuid4()
    agent = uuid4()
    events = [
        _event(agent_id=agent, problem_id=pid, created_at=now - timedelta(days=1))
    ]
    outcomes = [Outcome(solution_id=sid, reporter_id=agent, success=True)]
    rollup = compute_behavioral_signals(
        events,
        outcomes,
        solution_problem={sid: pid},
        seed_agent_ids=frozenset(),
        now=now,
    )
    assert rollup["outcome_followup_pairs"] == 1
    assert rollup["outcome_followup_share"] == 1.0


def test_outcome_predating_recall_is_not_a_followup() -> None:
    now = utc_now()
    pid = uuid4()
    sid = uuid4()
    agent = uuid4()
    events = [
        _event(agent_id=agent, problem_id=pid, created_at=now - timedelta(days=1))
    ]
    # The report landed BEFORE the first recall — it cannot be that recall's
    # follow-up.
    outcomes = [
        Outcome(
            solution_id=sid,
            reporter_id=agent,
            success=True,
            created_at=now - timedelta(days=2),
        )
    ]
    rollup = compute_behavioral_signals(
        events,
        outcomes,
        solution_problem={sid: pid},
        seed_agent_ids=frozenset(),
        now=now,
    )
    assert rollup["outcome_followup_pairs"] == 0


def test_silent_recall_has_no_followup() -> None:
    now = utc_now()
    pid = uuid4()
    agent = uuid4()
    events = [
        _event(agent_id=agent, problem_id=pid, created_at=now - timedelta(days=1))
    ]
    rollup = compute_behavioral_signals(
        events, [], solution_problem={}, seed_agent_ids=frozenset(), now=now
    )
    assert rollup["outcome_followup_pairs"] == 0
    assert rollup["outcome_followup_share"] == 0.0


def test_anonymous_callers_are_pairs_but_not_identifiable() -> None:
    now = utc_now()
    pid = uuid4()
    gap = timedelta(hours=2)
    events = [
        _event(ip_hash="ip-1", problem_id=pid, created_at=now - gap * 2),
        _event(ip_hash="ip-1", problem_id=pid, created_at=now - gap),
    ]
    rollup = compute_behavioral_signals(
        events, [], solution_problem={}, seed_agent_ids=frozenset(), now=now
    )
    assert rollup["recall_pairs"] == 1
    assert rollup["identifiable_pairs"] == 0
    assert rollup["repeat_query_pairs"] == 1
    assert rollup["outcome_followup_share"] is None


# --- Dashboard integration ----------------------------------------------------


def test_dashboard_includes_zeroed_section_when_no_query_repo_wired() -> None:
    service, author_id = _service_with_query_log()
    # Simulate DEMO_MODE / legacy boot where the repo is absent.
    service._query_events = None
    signals = _signals(service)
    for key, value in ZEROED.items():
        assert signals[key] == value, key


def test_dashboard_reports_live_pairs_end_to_end() -> None:
    service, author_id = _service_with_query_log()
    problem_id, solution_id = _seed_problem_with_solution(service, author_id)

    querier = service.register_agent(model_type="test")[0].agent_id
    first = utc_now() - timedelta(hours=3)
    second = utc_now() - timedelta(minutes=5)
    service._query_events.add(
        _event(agent_id=querier, problem_id=problem_id, created_at=first)
    )
    service._query_events.add(
        _event(agent_id=querier, problem_id=problem_id, created_at=second)
    )
    service._outcomes.add(
        Outcome(solution_id=solution_id, reporter_id=querier, success=True)
    )

    signals = _signals(service)
    assert signals["recall_pairs"] == 1
    assert signals["repeat_query_pairs"] == 1
    assert signals["identifiable_pairs"] == 1
    assert signals["outcome_followup_pairs"] == 1
