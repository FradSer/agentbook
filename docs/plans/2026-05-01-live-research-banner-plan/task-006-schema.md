# Task 006: LiveResearchSnapshotResponse + LiveResearchActiveItem schemas

**depends-on**: 005b

## Description

Add Pydantic response schemas for the REST snapshot endpoint and the SSE `snapshot` event payload. Schema-only task — no behaviour, no test pair needed (Pydantic validation itself is exercised by 007a). The schemas mirror the dict shape established by `get_live_research_snapshot()` so handlers stay dict-passthrough (consistent with existing dashboard endpoints).

## Execution Context

**Task Number**: 006 of 20
**Phase**: Presentation — Schemas
**Prerequisites**: Task 005b (service method is the source of truth for the shape).

## BDD Scenario

The schema underwrites every active-item assertion in:

```gherkin
Scenario: Event payload exposes only public fields
  When the server emits a "research_started" event
  Then the JSON payload contains keys "problem_id", "description",
    "solution_count", "best_confidence", "research_started_at", "now"
```

**Spec Source**: `../2026-05-01-live-research-banner-design/bdd-specs.md`

## Files to Modify/Create

- Modify: `backend/presentation/api/schemas.py`

## Steps

### Step 1: Add the two schemas

In `backend/presentation/api/schemas.py`:

```python
class LiveResearchActiveItem(BaseModel):
    problem_id: str
    description: str
    solution_count: int
    best_confidence: float
    research_started_at: datetime
    elapsed_seconds: int


class LiveResearchSnapshotResponse(BaseModel):
    active: list[LiveResearchActiveItem]
    last_cycle_at: datetime | None
    now: datetime
```

Match the style of the existing dashboard envelopes at lines 142-169 (e.g., `RadarApiResponse`, `ResearchCandidatesResponse`). Forbid extra fields: configure `model_config = {"extra": "forbid"}` so a typo on the service side surfaces immediately.

### Step 2: Re-export
Add both names to the module `__all__` if one is defined; otherwise just ensure they import cleanly via `from backend.presentation.api.schemas import LiveResearchSnapshotResponse, LiveResearchActiveItem`.

### Step 3: Verify import + serialisation
```bash
uv run python -c "
from backend.presentation.api.schemas import LiveResearchSnapshotResponse, LiveResearchActiveItem
from datetime import datetime, timezone
item = LiveResearchActiveItem(
    problem_id='abc', description='x', solution_count=1,
    best_confidence=0.5,
    research_started_at=datetime.now(timezone.utc),
    elapsed_seconds=10,
)
resp = LiveResearchSnapshotResponse(active=[item], last_cycle_at=None, now=datetime.now(timezone.utc))
print(resp.model_dump_json())
"
```

### Step 4: Format
```bash
uv run ruff format backend/presentation/api/schemas.py
uv run ruff check backend/presentation/api/schemas.py
```

## Verification Commands

```bash
uv run python -c "from backend.presentation.api.schemas import LiveResearchSnapshotResponse, LiveResearchActiveItem"
uv run ruff check backend/presentation/api/schemas.py
```

## Success Criteria

- Both classes exported from `backend.presentation.api.schemas`.
- Schemas configured with `extra='forbid'`.
- A round-trip `LiveResearchSnapshotResponse(...).model_dump_json()` succeeds with no validation errors.
- Ruff check passes.
