"""TTL LRU search cache used by AgentbookService.search_problems."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.application.service import AgentbookService
from backend.core.search_cache import TTLCache
from backend.domain.models import Problem
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)


class _FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _build_service_with_problem(description: str) -> AgentbookService:
    problems = InMemoryProblemRepository()
    problems.add(
        Problem(
            problem_id=uuid4(),
            author_id=uuid4(),
            description=description,
            created_at=datetime.now(UTC),
            last_activity_at=datetime.now(UTC),
            review_status="approved",
        )
    )
    return AgentbookService(
        agents=InMemoryAgentRepository(),
        problems=problems,
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )


def test_ttlcache_returns_stored_value_within_ttl() -> None:
    clock = _FakeClock()
    cache = TTLCache(maxsize=4, ttl=300, clock=clock)
    cache.set(("a",), "value-a")
    clock.advance(200)
    assert cache.get(("a",)) == "value-a"


def test_ttlcache_expires_entries_after_ttl() -> None:
    clock = _FakeClock()
    cache = TTLCache(maxsize=4, ttl=300, clock=clock)
    cache.set(("a",), "value-a")
    clock.advance(301)
    assert cache.get(("a",)) is None


def test_ttlcache_evicts_oldest_when_over_maxsize() -> None:
    clock = _FakeClock()
    cache = TTLCache(maxsize=2, ttl=300, clock=clock)
    cache.set(("a",), 1)
    cache.set(("b",), 2)
    cache.set(("c",), 3)
    assert cache.get(("a",)) is None
    assert cache.get(("b",)) == 2
    assert cache.get(("c",)) == 3


def test_ttlcache_lru_touches_on_get() -> None:
    clock = _FakeClock()
    cache = TTLCache(maxsize=2, ttl=300, clock=clock)
    cache.set(("a",), 1)
    cache.set(("b",), 2)
    cache.get(("a",))  # refresh a
    cache.set(("c",), 3)  # should evict b, not a
    assert cache.get(("a",)) == 1
    assert cache.get(("b",)) is None
    assert cache.get(("c",)) == 3


def test_service_caches_identical_query() -> None:
    service = _build_service_with_problem("TypeError json.dumps decimal")
    first = service.search_problems(query="typeerror json", limit=5)
    second = service.search_problems(query="typeerror json", limit=5)
    assert first is second
