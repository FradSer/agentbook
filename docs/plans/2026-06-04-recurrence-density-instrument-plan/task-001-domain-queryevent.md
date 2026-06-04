# Task 001: Domain QueryEvent model + QueryEventRepository Protocol

**depends-on**: (none)

## Description

Define the consumption-tracking domain contract: a `QueryEvent` value object and a `QueryEventRepository` Protocol. Pure domain layer — zero external imports, `@dataclass(slots=True)`, `typing.Protocol`. This is the contract every later task implements against. Foundation task (no Red/Green pairing).

## Execution Context

- **Layer:** Domain (`backend/domain/`). Must not import infrastructure or application code.
- **Type:** setup/foundation — no paired test task; its correctness is exercised by 002a onward.
- **Prereqs:** none.

## BDD Scenario

This foundation task has no design-`bdd-specs.md` scenario (it defines the contract the design's measurement scenario relies on). Contract-shape scenario:

```gherkin
Scenario: The domain exposes a QueryEvent and its repository contract
  Given the domain layer defines consumption tracking
  When a search or recall records what was queried and what it matched
  Then a QueryEvent captures: query text, caller identity (agent_id/ip_hash/fingerprint_hash),
    the top match (problem id, match quality, has_help), and the exclusion flags
    (is_self_hit, is_seed_replay, pattern_class_hit)
  And a QueryEventRepository Protocol declares add, add_with_dedup, and the
    recurrence aggregation methods, with no infrastructure dependency
```

## Files to Modify/Create

- `backend/domain/models.py` — add `QueryEvent` after `Outcome`.
- `backend/domain/repositories.py` — add `QueryEventRepository` Protocol after the last repository.

## Steps

1. Add the `QueryEvent` dataclass mirroring the existing `@dataclass(slots=True)` + `field(default_factory=...)` style. **Intent only — field set and shape are the contract; exact ordering may match house style:**

   ```python
   # Intent only — contract shape, not final formatting
   @dataclass(slots=True)
   class QueryEvent:
       query_text: str
       agent_id: UUID | None            # None for anonymous callers
       ip_hash: str | None
       fingerprint_hash: str | None
       top_match_problem_id: UUID | None  # primary hit; None when no good match
       top_match_quality: str | None      # "exact" | "strong" | "weak" | None
       has_help: bool                     # reliance target present on the top match
       is_self_hit: bool                  # querier == top-match contributor
       is_seed_replay: bool               # query replayed from the seed set
       pattern_class_hit: bool = False
       event_id: UUID = field(default_factory=uuid4)
       created_at: datetime = field(default_factory=utc_now)
   ```

2. Add the `QueryEventRepository` Protocol — **method signatures only, no bodies (Intent only):**

   ```python
   # Intent only — interface contract; implementations live in infrastructure
   class QueryEventRepository(Protocol):
       def add(self, event: QueryEvent) -> None: ...
       def add_with_dedup(
           self, event: QueryEvent, agents: "AgentRepository", *,
           exclude_seed_replay: bool = True, exclude_self_hits: bool = True,
           dedup_window_seconds: int = 600,
       ) -> bool: ...  # True if recorded, False if dropped by a dedup rule
       def list_all(self, since: datetime | None = None) -> list[QueryEvent]: ...
       def query_count_for_problem(self, problem_id: UUID, since: datetime | None = None) -> int: ...
       def recurrence_rollup(self, *, seed_agent_ids: frozenset[UUID] = frozenset()) -> dict: ...
   ```

3. Do not compute anything in the Protocol — it is an interface only. `recurrence_rollup`'s exact dict shape (`recurrence_density`, `organic_recurrence`, `total_independent_queries`, `per_problem`) is declared here and defined in tasks 002b/003b.

## Verification Commands

```bash
uv run python -c "from backend.domain.models import QueryEvent; from backend.domain.repositories import QueryEventRepository; print('ok')"
uv run ruff check backend/domain/models.py backend/domain/repositories.py
```

## Success Criteria

- Both symbols import cleanly with no side effects (domain stays infrastructure-free).
- `ruff` passes on both files.
- `QueryEvent` carries all flag fields the metric math needs (`top_match_quality`, `has_help`, `is_self_hit`, `is_seed_replay`); `QueryEventRepository` declares `add_with_dedup` and `recurrence_rollup`.
