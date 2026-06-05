"""Service-layer contract for the recurrence-density instrument.

Pins that ``search_problems`` records exactly one dedup'd ``QueryEvent`` per
search (deriving its flags from the computed rows), that recording is
best-effort (a recording failure never fails the search), and that
``get_recurrence_density`` shapes the repo rollup — excluding self-hits from
the numerator and returning the empty rollup when no ``query_events`` repo is
wired.

Feature file: backend/tests/features/recurrence-density.feature (the seed-set
exclusion guarantee enforced here at the service layer).
"""

from __future__ import annotations

from backend.application.service import CallerContext
from backend.tests.conftest import _build_service

_STRONG_DESC = "Docker daemon socket permission denied; fix via docker group membership"
_STRONG_SIG = (
    "permission denied while trying to connect to the Docker daemon socket "
    "at unix:///var/run/docker.sock"
)
_STRONG_QUERY = _STRONG_SIG
_STRONG_SOLUTION = (
    "Add the user to the docker group and restart the shell session "
    "so the socket becomes group-accessible."
)


def _seed_answered_problem(service, author_id):
    """Approved problem authored by ``author_id`` with one active solution,
    matchable at the strong/exact tier by ``_STRONG_QUERY``."""
    problem = service.create_problem(
        author_id=author_id,
        description=_STRONG_DESC,
        error_signature=_STRONG_SIG,
    )
    service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content=_STRONG_SOLUTION,
        steps=["add user to docker group", "re-login"],
    )
    return problem


# --- Scenario: a search records one event and the rollup reflects it -------


def test_search_records_one_event_and_rollup_counts_it():
    service, author_id = _build_service()
    problem = _seed_answered_problem(service, author_id)
    querier = service.register_agent("claude-sonnet-4-5")[0].agent_id

    payload = service.search_problems(
        query=_STRONG_QUERY,
        limit=10,
        caller=CallerContext(agent_id=querier),
    )
    assert payload["no_good_match"] is False

    events = service._query_events.list_all()
    assert len(events) == 1
    event = events[0]
    assert event.top_match_problem_id == problem.problem_id
    assert event.top_match_quality in ("strong", "exact")
    assert event.has_help is True
    assert event.is_self_hit is False

    rollup = service.get_recurrence_density()
    assert set(rollup) == {
        "recurrence_density",
        "organic_recurrence",
        "total_independent_queries",
        "problems",
    }
    assert rollup["total_independent_queries"] == 1
    assert rollup["recurrence_density"] > 0


# --- Scenario: a self-hit is recorded but excluded from the numerator ------


def test_self_hit_recorded_but_excluded_from_numerator():
    service, author_id = _build_service()
    _seed_answered_problem(service, author_id)

    payload = service.search_problems(
        query=_STRONG_QUERY,
        limit=10,
        caller=CallerContext(agent_id=author_id),
    )
    assert payload["no_good_match"] is False

    events = service._query_events.list_all()
    assert len(events) == 1
    assert events[0].is_self_hit is True

    rollup = service.get_recurrence_density()
    # The self-hit must not raise the recurrence-density numerator.
    assert rollup["recurrence_density"] == 0.0


# --- Scenario: a no-good-match search is denominator-only ------------------


def test_no_good_match_search_is_denominator_only():
    service, author_id = _build_service()
    querier = service.register_agent("claude-sonnet-4-5")[0].agent_id

    payload = service.search_problems(
        query="a completely unrelated query about a llama in a hammock",
        limit=10,
        caller=CallerContext(agent_id=querier),
    )
    assert payload["no_good_match"] is True

    events = service._query_events.list_all()
    assert len(events) == 1
    event = events[0]
    assert event.top_match_problem_id is None
    assert event.has_help is False
    assert event.is_self_hit is False

    rollup = service.get_recurrence_density()
    assert rollup["total_independent_queries"] == 1
    assert rollup["recurrence_density"] == 0.0


# --- Scenario: recording never breaks a search ----------------------------


class _RaisingQueryEvents:
    def add_with_dedup(self, *args, **kwargs):
        raise RuntimeError("recording backend is down")

    def recurrence_rollup(self, *, seed_agent_ids=frozenset()):
        raise RuntimeError("rollup backend is down")

    def list_all(self, since=None):
        return []


def test_recording_failure_never_breaks_search(caplog):
    service, author_id = _build_service()
    _seed_answered_problem(service, author_id)
    service._query_events = _RaisingQueryEvents()
    querier = service.register_agent("claude-sonnet-4-5")[0].agent_id

    payload = service.search_problems(
        query=_STRONG_QUERY,
        limit=10,
        caller=CallerContext(agent_id=querier),
    )

    # The search still returns its normal payload.
    assert payload["no_good_match"] is False
    assert payload["results"]
    # Best-effort instrumentation logs the swallowed error, never re-raises.
    assert any(record.levelno >= 30 for record in caplog.records), (
        "a swallowed recording error must be logged, not silently dropped"
    )


# --- Scenario: search works without a query_events repo --------------------


def test_search_works_without_query_events_repo():
    service, author_id = _build_service()
    service._query_events = None
    _seed_answered_problem(service, author_id)

    payload = service.search_problems(query=_STRONG_QUERY, limit=10)
    assert payload["no_good_match"] is False

    rollup = service.get_recurrence_density()
    assert rollup == {
        "recurrence_density": 0.0,
        "organic_recurrence": 0.0,
        "total_independent_queries": 0,
        "problems": [],
    }


# --- Scenario: default caller (no identity) still records ------------------


def test_search_without_caller_still_records_event():
    service, author_id = _build_service()
    _seed_answered_problem(service, author_id)

    payload = service.search_problems(query=_STRONG_QUERY, limit=10)
    assert payload["no_good_match"] is False

    events = service._query_events.list_all()
    assert len(events) == 1
    event = events[0]
    assert event.agent_id is None
    # An anonymous caller cannot be a self-hit (no identity to compare).
    assert event.is_self_hit is False
    assert event.has_help is True


# --- Scenario: distinct callers issuing the same cached query each count -----


def test_cache_hit_still_records_event_for_a_distinct_caller():
    """A result served from the latency cache must not hide the caller's query.

    The search cache is keyed on the query terms only, so a second agent asking
    the identical recalled question is served from cache. If recording were
    gated behind the cache miss, that second hit -- the cross-agent repeat that
    *is* organic recurrence -- would vanish from the instrument.
    """
    service, author_id = _build_service()
    _seed_answered_problem(service, author_id)
    agent_a = service.register_agent("claude-sonnet-4-5")[0].agent_id
    agent_b = service.register_agent("gpt-oss-20b")[0].agent_id

    first = service.search_problems(
        query=_STRONG_QUERY, limit=10, caller=CallerContext(agent_id=agent_a)
    )
    # The second caller asks the identical query; it is served from the cache.
    second = service.search_problems(
        query=_STRONG_QUERY, limit=10, caller=CallerContext(agent_id=agent_b)
    )
    assert second == first, "the identical query must be served from the cache"

    events = service._query_events.list_all()
    assert {e.agent_id for e in events} == {agent_a, agent_b}

    rollup = service.get_recurrence_density()
    assert rollup["total_independent_queries"] == 2


# --- Scenario: a hit on a seed-contributed entry is not organic --------------


def test_strong_hit_on_seed_contributed_entry_is_not_organic():
    """A real agent hitting a seed-contributed entry is a bootstrap hit: it
    counts toward recurrence_density but must be excluded from organic_recurrence
    (the contributor is a seed, not a peer), so seeded hits cannot inflate the
    network-effect signal that gates multiplayer."""
    service, _author = _build_service()
    seed_id = service.register_agent("seed-corpus")[0].agent_id
    # Treat this agent as the seed/operator identity for the rollup.
    service._seed_agent_ids = lambda: frozenset({seed_id})
    # The reliance target is contributed by the seed agent.
    _seed_answered_problem(service, seed_id)

    real_id = service.register_agent("real-weak-agent")[0].agent_id
    payload = service.search_problems(
        query=_STRONG_QUERY, limit=10, caller=CallerContext(agent_id=real_id)
    )
    assert payload["no_good_match"] is False

    events = service._query_events.list_all()
    assert len(events) == 1
    event = events[0]
    assert event.is_self_hit is False
    assert event.is_seeded_hit is True  # matched contributor is a seed agent

    rollup = service.get_recurrence_density()
    # The book held an actionable answer -> recurrence_density counts it.
    assert rollup["recurrence_density"] > 0
    # ...but the contributor is a seed, so it is NOT a network effect.
    assert rollup["organic_recurrence"] == 0.0
