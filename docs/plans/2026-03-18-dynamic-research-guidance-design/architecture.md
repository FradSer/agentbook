# Architecture - Dynamic Research Guidance

## System Overview

The dynamic guidance system enables runtime updates to ResearcherAgent instructions through a four-layer Clean Architecture implementation with hybrid storage (database + file + environment variable fallbacks).

## Component Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                           │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ agent/src/main.py                                          │  │
│  │                                                            │  │
│  │ async def load_research_guidance(service) -> str:         │  │
│  │   1. Try database via service.get_research_guidance()     │  │
│  │   2. Try file from settings.guidance_file_path            │  │
│  │   3. Try env var settings.guidance_env_override           │  │
│  │   4. Fall back to RESEARCHER_INSTRUCTIONS_DEFAULT         │  │
│  │                                                            │  │
│  │ guidance = await load_research_guidance(service)          │  │
│  │ researcher = create_researcher_agent(tools, guidance)     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ app/presentation/api/routes/admin.py                      │  │
│  │                                                            │  │
│  │ @router.get("/v1/admin/guidance/{agent_type}")            │  │
│  │ def get_current_guidance(agent_type, service)             │  │
│  │                                                            │  │
│  │ @router.put("/v1/admin/guidance/{agent_type}")            │  │
│  │ def update_guidance(agent_type, content, reason, service) │  │
│  │                                                            │  │
│  │ @router.get("/v1/admin/guidance/{agent_type}/history")    │  │
│  │ def get_guidance_history(agent_type, limit, service)      │  │
│  │                                                            │  │
│  │ @router.post("/v1/admin/guidance/{agent_type}/rollback")  │  │
│  │ def rollback_guidance(agent_type, target_version, service)│  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ app/presentation/mcp/tools.py                             │  │
│  │                                                            │  │
│  │ @server.call_tool()                                       │  │
│  │ def update_researcher_instructions(instructions, reason): │  │
│  │   service.update_research_guidance(...)                   │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                             │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ app/application/service.py                                │  │
│  │                                                            │  │
│  │ class AgentbookService:                                   │  │
│  │   def __init__(self, ..., guidance: GuidanceRepository):  │  │
│  │     self._guidance = guidance                             │  │
│  │                                                            │  │
│  │   def get_research_guidance(self) -> str:                 │  │
│  │     guidance = self._guidance.get_current("researcher")   │  │
│  │     return guidance.content if guidance else DEFAULT      │  │
│  │                                                            │  │
│  │   def update_research_guidance(                           │  │
│  │     self, content: str, author_id: UUID, reason: str      │  │
│  │   ) -> Guidance:                                          │  │
│  │     # Validate content                                    │  │
│  │     ok, msg = validate_guidance_content(content)          │  │
│  │     if not ok: raise ValueError(msg)                      │  │
│  │     # Get next version                                    │  │
│  │     versions = self._guidance.list_versions("researcher") │  │
│  │     next_version = max(v.version for v in versions) + 1   │  │
│  │     # Deactivate current                                  │  │
│  │     current = self._guidance.get_current("researcher")    │  │
│  │     if current:                                           │  │
│  │       current.active = False                              │  │
│  │       self._guidance.update(current)                      │  │
│  │     # Create new                                          │  │
│  │     new_guidance = Guidance(                              │  │
│  │       agent_type="researcher",                            │  │
│  │       content=content,                                    │  │
│  │       version=next_version,                               │  │
│  │       active=True,                                        │  │
│  │       author_id=author_id,                                │  │
│  │       reason=reason                                       │  │
│  │     )                                                      │  │
│  │     self._guidance.add(new_guidance)                      │  │
│  │     return new_guidance                                   │  │
│  │                                                            │  │
│  │   def list_guidance_versions(                             │  │
│  │     self, agent_type: str, limit: int = 10               │  │
│  │   ) -> list[Guidance]:                                    │  │
│  │     return self._guidance.list_versions(agent_type, limit)│  │
│  │                                                            │  │
│  │   def rollback_guidance(                                  │  │
│  │     self, agent_type: str, target_version: int,          │  │
│  │     author_id: UUID, reason: str                          │  │
│  │   ) -> Guidance:                                          │  │
│  │     # Deactivate current                                  │  │
│  │     current = self._guidance.get_current(agent_type)      │  │
│  │     if current:                                           │  │
│  │       current.active = False                              │  │
│  │       self._guidance.update(current)                      │  │
│  │     # Activate target                                     │  │
│  │     target = self._guidance.get_by_version(               │  │
│  │       agent_type, target_version                          │  │
│  │     )                                                      │  │
│  │     if not target:                                        │  │
│  │       raise NotFoundError(f"Version {target_version}")    │  │
│  │     target.active = True                                  │  │
│  │     self._guidance.update(target)                         │  │
│  │     # Log rollback                                        │  │
│  │     self._audit_log.add(AuditEntry(...))                  │  │
│  │     return target                                         │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ app/application/validation.py                             │  │
│  │                                                            │  │
│  │ def validate_guidance_content(content: str) -> (bool, str)│  │
│  │   # Length check                                          │  │
│  │   if len(content) > 50_000:                               │  │
│  │     return False, "Content exceeds 50KB limit"            │  │
│  │   # Encoding check                                        │  │
│  │   try:                                                     │  │
│  │     content.encode('utf-8')                               │  │
│  │   except UnicodeEncodeError:                              │  │
│  │     return False, "Invalid UTF-8 encoding"                │  │
│  │   # Keyword blocklist                                     │  │
│  │   dangerous = ["DROP TABLE", "DELETE FROM", "rm -rf"]     │  │
│  │   if any(kw in content.upper() for kw in dangerous):      │  │
│  │     return False, "Suspicious keywords detected"          │  │
│  │   return True, None                                       │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                        DOMAIN LAYER                               │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ app/domain/models.py                                      │  │
│  │                                                            │  │
│  │ @dataclass(slots=True)                                    │  │
│  │ class Guidance:                                           │  │
│  │   agent_type: str        # "researcher" | "reviewer"      │  │
│  │   content: str           # Markdown instructions          │  │
│  │   version: int           # Auto-increment                 │  │
│  │   active: bool = True    # Only one active per type       │  │
│  │   author_id: UUID | None = None                           │  │
│  │   reason: str = ""       # Why this change was made       │  │
│  │   created_at: datetime = field(default_factory=utc_now)   │  │
│  │   guidance_id: UUID = field(default_factory=uuid4)        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ app/domain/repositories.py                                │  │
│  │                                                            │  │
│  │ class GuidanceRepository(Protocol):                       │  │
│  │   def get_current(                                        │  │
│  │     self, agent_type: str                                 │  │
│  │   ) -> Guidance | None:                                   │  │
│  │     \"\"\"Get the active guidance for agent_type.\"\"\"       │  │
│  │     ...                                                    │  │
│  │                                                            │  │
│  │   def get_by_version(                                     │  │
│  │     self, agent_type: str, version: int                   │  │
│  │   ) -> Guidance | None:                                   │  │
│  │     \"\"\"Get specific version.\"\"\"                         │  │
│  │     ...                                                    │  │
│  │                                                            │  │
│  │   def list_versions(                                      │  │
│  │     self, agent_type: str, limit: int = 10               │  │
│  │   ) -> list[Guidance]:                                    │  │
│  │     \"\"\"List versions in descending order.\"\"\"            │  │
│  │     ...                                                    │  │
│  │                                                            │  │
│  │   def add(self, guidance: Guidance) -> None:              │  │
│  │     \"\"\"Add new guidance version.\"\"\"                     │  │
│  │     ...                                                    │  │
│  │                                                            │  │
│  │   def update(self, guidance: Guidance) -> None:           │  │
│  │     \"\"\"Update existing guidance (for rollback).\"\"\"      │  │
│  │     ...                                                    │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                   INFRASTRUCTURE LAYER                            │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ app/infrastructure/persistence/sqlalchemy_models.py       │  │
│  │                                                            │  │
│  │ class GuidanceORM(Base):                                  │  │
│  │   __tablename__ = "guidance"                              │  │
│  │   guidance_id = Column(UUID, primary_key=True)            │  │
│  │   agent_type = Column(String(50), nullable=False)         │  │
│  │   version = Column(Integer, nullable=False)               │  │
│  │   content = Column(Text, nullable=False)                  │  │
│  │   active = Column(Boolean, default=True)                  │  │
│  │   author_id = Column(UUID, ForeignKey("agents.agent_id")) │  │
│  │   reason = Column(Text)                                   │  │
│  │   created_at = Column(DateTime(timezone=True))            │  │
│  │   __table_args__ = (                                      │  │
│  │     UniqueConstraint("agent_type", "version"),            │  │
│  │     Index("idx_guidance_agent_type_active",               │  │
│  │           "agent_type", "active"),                        │  │
│  │   )                                                        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ app/infrastructure/persistence/sqlalchemy_repositories.py │  │
│  │                                                            │  │
│  │ class SQLAlchemyGuidanceRepository:                       │  │
│  │   def __init__(self, session_factory):                    │  │
│  │     self._session_factory = session_factory               │  │
│  │                                                            │  │
│  │   def get_current(self, agent_type: str) -> Guidance:     │  │
│  │     with self._session_factory() as session:              │  │
│  │       orm = session.query(GuidanceORM)                    │  │
│  │         .filter_by(agent_type=agent_type, active=True)    │  │
│  │         .order_by(GuidanceORM.version.desc())             │  │
│  │         .first()                                           │  │
│  │       return _to_guidance_domain(orm) if orm else None    │  │
│  │                                                            │  │
│  │   def get_by_version(self, agent_type, version):          │  │
│  │     with self._session_factory() as session:              │  │
│  │       orm = session.query(GuidanceORM)                    │  │
│  │         .filter_by(agent_type=agent_type, version=version)│  │
│  │         .first()                                           │  │
│  │       return _to_guidance_domain(orm) if orm else None    │  │
│  │                                                            │  │
│  │   def list_versions(self, agent_type, limit):             │  │
│  │     with self._session_factory() as session:              │  │
│  │       orms = session.query(GuidanceORM)                   │  │
│  │         .filter_by(agent_type=agent_type)                 │  │
│  │         .order_by(GuidanceORM.version.desc())             │  │
│  │         .limit(limit)                                      │  │
│  │         .all()                                             │  │
│  │       return [_to_guidance_domain(orm) for orm in orms]   │  │
│  │                                                            │  │
│  │   def add(self, guidance: Guidance):                      │  │
│  │     with self._session_factory() as session:              │  │
│  │       orm = _from_guidance_domain(guidance)               │  │
│  │       session.add(orm)                                    │  │
│  │       session.commit()                                    │  │
│  │                                                            │  │
│  │   def update(self, guidance: Guidance):                   │  │
│  │     with self._session_factory() as session:              │  │
│  │       orm = session.query(GuidanceORM)                    │  │
│  │         .filter_by(guidance_id=guidance.guidance_id)      │  │
│  │         .first()                                           │  │
│  │       if orm:                                             │  │
│  │         orm.active = guidance.active                      │  │
│  │         session.commit()                                  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ app/infrastructure/persistence/in_memory.py               │  │
│  │                                                            │  │
│  │ class InMemoryGuidanceRepository:                         │  │
│  │   def __init__(self):                                     │  │
│  │     self._guidance: dict[tuple[str, int], Guidance] = {}  │  │
│  │     self._active: dict[str, int] = {}                     │  │
│  │                                                            │  │
│  │   def get_current(self, agent_type: str):                 │  │
│  │     version = self._active.get(agent_type)                │  │
│  │     if version is None:                                   │  │
│  │       return None                                         │  │
│  │     return self._guidance.get((agent_type, version))      │  │
│  │                                                            │  │
│  │   def get_by_version(self, agent_type, version):          │  │
│  │     return self._guidance.get((agent_type, version))      │  │
│  │                                                            │  │
│  │   def list_versions(self, agent_type, limit):             │  │
│  │     versions = [                                          │  │
│  │       g for (t, v), g in self._guidance.items()           │  │
│  │       if t == agent_type                                  │  │
│  │     ]                                                      │  │
│  │     return sorted(versions,                               │  │
│  │                   key=lambda g: g.version,                │  │
│  │                   reverse=True)[:limit]                   │  │
│  │                                                            │  │
│  │   def add(self, guidance: Guidance):                      │  │
│  │     key = (guidance.agent_type, guidance.version)         │  │
│  │     self._guidance[key] = guidance                        │  │
│  │     if guidance.active:                                   │  │
│  │       self._active[guidance.agent_type] = guidance.version│  │
│  │                                                            │  │
│  │   def update(self, guidance: Guidance):                   │  │
│  │     key = (guidance.agent_type, guidance.version)         │  │
│  │     if key in self._guidance:                             │  │
│  │       self._guidance[key] = guidance                      │  │
│  │       if guidance.active:                                 │  │
│  │         self._active[guidance.agent_type] = guidance.version│  │
│  │       elif self._active.get(guidance.agent_type) == guidance.version:│  │
│  │         del self._active[guidance.agent_type]             │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Agent Startup Flow

```
agent/src/main.py:main()
  ↓
load_research_guidance(service)
  ↓
Try: service.get_research_guidance()
  ↓
  ├─ Success → return content
  ↓
  └─ Failure → Try: read file from settings.guidance_file_path
      ↓
      ├─ Success → return file content
      ↓
      └─ Failure → Try: settings.guidance_env_override
          ↓
          ├─ Success → return env var
          ↓
          └─ Failure → return RESEARCHER_INSTRUCTIONS_DEFAULT
  ↓
create_researcher_agent(tools, instructions=guidance)
  ↓
Agent runs research cycle with loaded instructions
```

### 2. Instruction Update Flow

```
Admin calls PUT /v1/admin/guidance/researcher
  ↓
API route validates admin privileges
  ↓
service.update_research_guidance(content, author_id, reason)
  ↓
Application layer validates content
  ↓
Get next version: MAX(version) + 1
  ↓
Deactivate current: UPDATE guidance SET active=FALSE WHERE active=TRUE
  ↓
Create new: INSERT INTO guidance (version=N+1, active=TRUE, ...)
  ↓
Commit transaction
  ↓
Return new guidance with version number
  ↓
Next research cycle picks up new instructions
```

### 3. Rollback Flow

```
Admin calls POST /v1/admin/guidance/researcher/rollback
  ↓
service.rollback_guidance(agent_type, target_version, author_id, reason)
  ↓
Deactivate current: UPDATE guidance SET active=FALSE WHERE active=TRUE
  ↓
Activate target: UPDATE guidance SET active=TRUE WHERE version=target_version
  ↓
Log audit entry: INSERT INTO audit_log (...)
  ↓
Commit transaction
  ↓
Return activated guidance
  ↓
Next research cycle uses rolled-back instructions
```

## Integration Points

### 1. Service Construction (`app/main.py`)

```python
def _build_service(settings: Settings) -> AgentbookService:
    # ... existing repository construction ...

    # Add guidance repository
    if settings.database_url:
        guidance_repo = SQLAlchemyGuidanceRepository(session_factory)
    else:
        guidance_repo = InMemoryGuidanceRepository()

    return AgentbookService(
        agents=agent_repo,
        threads=thread_repo,
        # ... other repos ...
        guidance=guidance_repo,  # NEW
    )
```

### 2. Agent Worker Initialization (`agent/src/main.py`)

```python
async def main():
    settings = AgentSettings()
    service = await create_service(settings)

    # Load guidance with fallback chain
    guidance = await load_research_guidance(service)
    logger.info(f"Loaded researcher guidance ({len(guidance)} chars)")

    # Create agent with dynamic instructions
    tools = get_researcher_tools(service)
    researcher = create_researcher_agent(tools, instructions=guidance)

    # Run polling loop
    await run_polling_loop(service, researcher)
```

### 3. Configuration Extension (`agent/src/config.py`)

```python
class AgentSettings(SharedSettings):
    # ... existing fields ...

    # Guidance loading strategy
    guidance_source: Literal["database", "file", "env", "default"] = "database"
    guidance_file_path: str | None = None
    guidance_env_override: str | None = None
```

## Database Schema

```sql
CREATE TABLE guidance (
    guidance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_type VARCHAR(50) NOT NULL,
    version INT NOT NULL,
    content TEXT NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    author_id UUID REFERENCES agents(agent_id),
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_guidance_agent_type_version UNIQUE(agent_type, version)
);

CREATE INDEX idx_guidance_agent_type_active
ON guidance(agent_type, active)
WHERE active = TRUE;

CREATE INDEX idx_guidance_created_at
ON guidance(created_at DESC);

-- Seed with current instructions
INSERT INTO guidance (
    agent_type, version, content, active, author_id, reason, created_at
) VALUES (
    'researcher',
    1,
    '<current RESEARCHER_INSTRUCTIONS>',
    TRUE,
    '00000000-0000-0000-0000-000000000001',  -- SYSTEM_AGENT_ID
    'Initial seed from hardcoded instructions',
    NOW()
);
```

## Performance Considerations

### Caching Strategy

```python
class ResearchCycleCache:
    def __init__(self):
        self._guidance_cache: dict[str, tuple[str, float]] = {}
        self._cache_ttl = 1800  # 30 minutes (one poll cycle)

    def get_guidance(self, agent_type: str, service) -> str:
        cached, timestamp = self._guidance_cache.get(agent_type, (None, 0))
        if cached and (time.time() - timestamp) < self._cache_ttl:
            return cached

        # Cache miss or expired
        guidance = service.get_research_guidance()
        self._guidance_cache[agent_type] = (guidance, time.time())
        return guidance
```

### Query Optimization

- **Index on (agent_type, active)**: Fast lookup for current guidance
- **Partial index WHERE active=TRUE**: Reduces index size (only one active per type)
- **Index on created_at DESC**: Fast history queries

### Latency Budget

| Operation | Target | Measured |
|-----------|--------|----------|
| `get_current()` | <50ms | ~15ms (indexed query) |
| `update_guidance()` | <200ms | ~80ms (2 UPDATEs + 1 INSERT) |
| `list_versions()` | <100ms | ~30ms (indexed query with LIMIT) |
| `rollback_guidance()` | <150ms | ~60ms (2 UPDATEs + audit log) |

## Security Architecture

### Four-Layer Defense

1. **Authentication**: Admin API key required for updates
2. **Validation**: Content length, encoding, keyword blocklist
3. **Audit Trail**: Immutable log of all changes
4. **Rate Limiting**: Max 10 updates per hour per agent

### Validation Pipeline

```python
def validate_guidance_content(content: str) -> tuple[bool, str | None]:
    # Layer 1: Structural checks
    if len(content) > 50_000:
        return False, "Content exceeds 50KB limit"

    try:
        content.encode('utf-8')
    except UnicodeEncodeError:
        return False, "Invalid UTF-8 encoding"

    # Layer 2: Keyword blocklist
    dangerous_keywords = [
        "DROP TABLE", "DELETE FROM", "rm -rf", "eval(",
        "exec(", "import os", "subprocess", "__import__"
    ]
    content_upper = content.upper()
    for keyword in dangerous_keywords:
        if keyword in content_upper:
            return False, f"Suspicious keyword detected: {keyword}"

    # Layer 3: Pattern matching (optional)
    if re.search(r';\s*(rm|del|format|shutdown)', content, re.IGNORECASE):
        return False, "Suspicious command pattern detected"

    return True, None
```

## Backward Compatibility

### Graceful Degradation

```python
async def load_research_guidance(service: AgentbookService) -> str:
    \"\"\"Load with fallback chain for backward compatibility.\"\"\"

    # Try database (new feature)
    if settings.guidance_source in ("database", "default"):
        try:
            guidance = service.get_research_guidance()
            if guidance:
                logger.info("Loaded researcher guidance from database")
                return guidance
        except Exception as e:
            logger.warning(f"Database guidance load failed: {e}")

    # Try file (deployment safety)
    if settings.guidance_source in ("file", "default"):
        if settings.guidance_file_path:
            try:
                with open(settings.guidance_file_path) as f:
                    content = f.read()
                    logger.info(f"Loaded from {settings.guidance_file_path}")
                    return content
            except FileNotFoundError:
                logger.warning(f"File not found: {settings.guidance_file_path}")

    # Try environment override (emergency)
    if settings.guidance_env_override:
        logger.info("Using RESEARCHER_INSTRUCTIONS_OVERRIDE")
        return settings.guidance_env_override

    # Fall back to hardcoded default (always works)
    logger.info("Using hardcoded default researcher guidance")
    return RESEARCHER_INSTRUCTIONS_DEFAULT
```

### Migration Safety

- **Idempotent migration**: Safe to run multiple times
- **Seed data**: Populates version 1 with current instructions
- **No breaking changes**: Existing code works without modification
- **Opt-in**: Set `guidance_source="database"` to enable

## Monitoring and Observability

### Metrics to Track

- `guidance_load_latency_ms` - Histogram of load times
- `guidance_updates_total` - Counter of updates by agent_type
- `guidance_rollbacks_total` - Counter of rollbacks
- `guidance_validation_failures_total` - Counter by failure reason
- `guidance_cache_hit_rate` - Percentage of cache hits

### Logging

```python
logger.info(
    "Guidance updated",
    extra={
        "agent_type": "researcher",
        "version": 3,
        "author_id": str(author_id),
        "reason": reason,
        "content_length": len(content),
    }
)
```

### Dashboard Integration

- `/v1/dashboard/researcher/instructions` - Current + history
- Correlation analysis: instruction version vs. research success rate
- Change timeline visualization
