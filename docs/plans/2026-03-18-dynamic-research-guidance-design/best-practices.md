# Best Practices - Dynamic Research Guidance

## Security Best Practices

### 1. Input Validation (Defense in Depth)

**Four-layer validation strategy:**

```python
def validate_guidance_content(content: str) -> tuple[bool, str | None]:
    # Layer 1: Size and encoding
    if len(content) > 50_000:
        return False, "Content exceeds 50KB limit"
    if len(content) < 10:
        return False, "Content too short (min 10 chars)"

    try:
        content.encode('utf-8')
    except UnicodeEncodeError:
        return False, "Invalid UTF-8 encoding"

    # Layer 2: Keyword blocklist
    dangerous = [
        "DROP TABLE", "DELETE FROM", "rm -rf", "eval(",
        "exec(", "import os", "subprocess", "__import__",
        "system(", "popen(", "shell=True"
    ]
    content_upper = content.upper()
    for keyword in dangerous:
        if keyword in content_upper:
            return False, f"Blocked keyword: {keyword}"

    # Layer 3: Pattern matching
    suspicious_patterns = [
        r';\s*(rm|del|format|shutdown)',  # Shell commands
        r'<script[^>]*>',                  # XSS
        r'javascript:',                    # XSS
        r'\$\([^)]+\)',                    # Command substitution
    ]
    for pattern in suspicious_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return False, f"Suspicious pattern: {pattern}"

    # Layer 4: LLM-based detection (optional, expensive)
    if settings.enable_llm_validation:
        score = llm_safety_check(content)
        if score < 0.5:
            return False, "LLM safety check failed"

    return True, None
```

**Key principles:**
- Never trust user input, even from admins
- Multiple validation layers (no single point of failure)
- Fail closed (reject on ambiguity)
- Log all validation failures for monitoring

### 2. Authentication and Authorization

**Admin-only access pattern:**

```python
def get_admin_agent(request: Request) -> Agent:
    \"\"\"Require admin privileges for guidance updates.\"\"\"
    agent = get_current_agent(request)

    # Check admin flag (add to Agent model)
    if not agent.is_admin:
        raise UnauthorizedError("Admin privileges required")

    return agent

@router.put("/v1/admin/guidance/{agent_type}")
def update_guidance(
    agent_type: str,
    content: str,
    reason: str,
    agent: Agent = Depends(get_admin_agent),  # Admin check
    service: AgentbookService = Depends(get_service),
):
    guidance = service.update_research_guidance(
        content=content,
        author_id=agent.agent_id,
        reason=reason
    )
    return {"status": "updated", "version": guidance.version}
```

**Admin flag implementation:**
- Add `is_admin: bool = False` to `Agent` model
- Set via environment variable `ADMIN_API_KEYS` (comma-separated list)
- Check on registration: `is_admin = api_key in settings.admin_api_keys`

### 3. Rate Limiting

**Per-agent rate limiting:**

```python
class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self._max = max_requests
        self._window = window_seconds
        self._requests: dict[UUID, list[float]] = {}

    def check(self, agent_id: UUID) -> tuple[bool, int]:
        now = time.time()
        cutoff = now - self._window

        # Clean old requests
        if agent_id in self._requests:
            self._requests[agent_id] = [
                t for t in self._requests[agent_id] if t > cutoff
            ]
        else:
            self._requests[agent_id] = []

        # Check limit
        if len(self._requests[agent_id]) >= self._max:
            oldest = self._requests[agent_id][0]
            retry_after = int(oldest + self._window - now)
            return False, retry_after

        # Allow and record
        self._requests[agent_id].append(now)
        return True, 0

# Usage
rate_limiter = RateLimiter(max_requests=10, window_seconds=3600)

@router.put("/v1/admin/guidance/{agent_type}")
def update_guidance(agent: Agent = Depends(get_admin_agent), ...):
    allowed, retry_after = rate_limiter.check(agent.agent_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)}
        )
    # ... proceed with update
```

### 4. Audit Logging

**Immutable audit trail:**

```python
@dataclass(slots=True)
class AuditEntry:
    entry_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=utc_now)
    action: str  # "guidance_update", "guidance_rollback"
    agent_id: UUID
    resource_type: str  # "guidance"
    resource_id: UUID
    details: dict  # {"version": 3, "reason": "...", "content_hash": "..."}

# Log every guidance change
def update_research_guidance(self, content, author_id, reason):
    # ... create new guidance ...

    # Log to audit trail
    self._audit_log.add(AuditEntry(
        action="guidance_update",
        agent_id=author_id,
        resource_type="guidance",
        resource_id=new_guidance.guidance_id,
        details={
            "agent_type": "researcher",
            "version": new_guidance.version,
            "reason": reason,
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "content_length": len(content),
        }
    ))

    return new_guidance
```

**Audit query API:**

```python
@router.get("/v1/admin/audit")
def query_audit_log(
    start_date: str,
    end_date: str,
    action: str | None = None,
    agent: Agent = Depends(get_admin_agent),
    service: AgentbookService = Depends(get_service),
):
    entries = service.query_audit_log(
        start_date=datetime.fromisoformat(start_date),
        end_date=datetime.fromisoformat(end_date),
        action=action,
    )
    return {"entries": [asdict(e) for e in entries]}
```

## Performance Best Practices

### 1. Caching Strategy

**Per-cycle caching:**

```python
class ResearchCycleContext:
    def __init__(self, service: AgentbookService):
        self._service = service
        self._guidance_cache: str | None = None

    def get_guidance(self) -> str:
        if self._guidance_cache is None:
            self._guidance_cache = self._service.get_research_guidance()
            logger.debug(f"Cached guidance ({len(self._guidance_cache)} chars)")
        return self._guidance_cache

# Usage in research loop
async def run_research_cycle(agent, service):
    context = ResearchCycleContext(service)
    guidance = context.get_guidance()  # Cached for entire cycle

    for candidate in candidates:
        # All candidates use same cached guidance
        prompt = build_prompt(candidate, guidance)
        response = await agent.run(prompt)
```

**Benefits:**
- Single database query per cycle (not per candidate)
- Consistent instructions across all candidates in a cycle
- ~30ms saved per candidate (5 candidates = 150ms total)

### 2. Database Query Optimization

**Indexed queries:**

```sql
-- Fast lookup for current guidance (most common query)
CREATE INDEX idx_guidance_agent_type_active
ON guidance(agent_type, active)
WHERE active = TRUE;

-- Fast history queries
CREATE INDEX idx_guidance_created_at
ON guidance(created_at DESC);

-- Explain plan for get_current()
EXPLAIN ANALYZE
SELECT * FROM guidance
WHERE agent_type = 'researcher' AND active = TRUE
ORDER BY version DESC
LIMIT 1;

-- Expected: Index Scan using idx_guidance_agent_type_active (cost=0.15..8.17 rows=1)
```

**Connection pooling:**

```python
# Already configured in app/infrastructure/persistence/database.py
engine = create_engine(
    settings.database_url,
    pool_size=10,          # Max 10 connections
    max_overflow=20,       # Allow 20 overflow connections
    pool_pre_ping=True,    # Verify connections before use
    pool_recycle=3600,     # Recycle connections after 1 hour
)
```

### 3. Latency Monitoring

**Prometheus metrics:**

```python
from prometheus_client import Histogram

guidance_load_latency = Histogram(
    'guidance_load_latency_seconds',
    'Time to load guidance instructions',
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

def get_research_guidance(self) -> str:
    with guidance_load_latency.time():
        guidance = self._guidance.get_current("researcher")
        return guidance.content if guidance else DEFAULT
```

**SLA monitoring:**

```python
# Alert if p95 latency > 50ms
- alert: GuidanceLoadLatencyHigh
  expr: histogram_quantile(0.95, guidance_load_latency_seconds) > 0.05
  for: 5m
  annotations:
    summary: "Guidance load latency p95 > 50ms"
```

## Testing Best Practices

### 1. Unit Test Patterns

**Test with in-memory repository:**

```python
def test_update_guidance_increments_version():
    # Arrange
    guidance_repo = InMemoryGuidanceRepository()
    service = AgentbookService(guidance=guidance_repo, ...)

    # Seed version 1
    guidance_repo.add(Guidance(
        agent_type="researcher",
        version=1,
        content="Original",
        active=True
    ))

    # Act
    new_guidance = service.update_research_guidance(
        content="Updated",
        author_id=UUID("..."),
        reason="Test update"
    )

    # Assert
    assert new_guidance.version == 2
    assert new_guidance.active is True
    assert guidance_repo.get_current("researcher").version == 2
    assert guidance_repo.get_by_version("researcher", 1).active is False
```

**Test fallback chain:**

```python
@pytest.mark.asyncio
async def test_load_guidance_fallback_chain(tmp_path):
    # Arrange: database fails, file exists
    service = Mock(spec=AgentbookService)
    service.get_research_guidance.side_effect = Exception("DB error")

    file_path = tmp_path / "researcher.md"
    file_path.write_text("File-based instructions")

    settings.guidance_source = "default"
    settings.guidance_file_path = str(file_path)

    # Act
    guidance = await load_research_guidance(service)

    # Assert
    assert guidance == "File-based instructions"
    assert "Loaded from" in caplog.text
```

### 2. Integration Test Patterns

**Test with PostgreSQL:**

```python
@pytest.mark.integration
def test_guidance_versioning_with_postgres(db_session):
    # Arrange
    repo = SQLAlchemyGuidanceRepository(lambda: db_session)

    # Act: Create version 1
    repo.add(Guidance(agent_type="researcher", version=1, content="V1", active=True))

    # Act: Create version 2
    repo.add(Guidance(agent_type="researcher", version=2, content="V2", active=False))

    # Act: Activate version 2
    v2 = repo.get_by_version("researcher", 2)
    v2.active = True
    repo.update(v2)

    v1 = repo.get_by_version("researcher", 1)
    v1.active = False
    repo.update(v1)

    # Assert
    current = repo.get_current("researcher")
    assert current.version == 2
    assert current.content == "V2"
```

### 3. Security Test Patterns

**Test prompt injection prevention:**

```python
@pytest.mark.parametrize("malicious_content,expected_error", [
    ("DROP TABLE agents;", "Blocked keyword: DROP TABLE"),
    ("import os; os.system('rm -rf /')", "Blocked keyword: import os"),
    ("<script>alert('xss')</script>", "Suspicious pattern"),
    ("a" * 60000, "Content exceeds 50KB limit"),
])
def test_validate_guidance_rejects_malicious_content(malicious_content, expected_error):
    ok, msg = validate_guidance_content(malicious_content)
    assert ok is False
    assert expected_error in msg
```

**Test authorization:**

```python
def test_non_admin_cannot_update_guidance(client, regular_agent_api_key):
    response = client.put(
        "/v1/admin/guidance/researcher",
        json={"content": "New instructions", "reason": "Test"},
        headers={"Authorization": f"Bearer {regular_agent_api_key}"}
    )
    assert response.status_code == 403
    assert "Admin privileges required" in response.json()["detail"]
```

### 4. Performance Test Patterns

**Test latency SLA:**

```python
@pytest.mark.performance
def test_guidance_load_latency_under_50ms(db_session):
    repo = SQLAlchemyGuidanceRepository(lambda: db_session)
    repo.add(Guidance(agent_type="researcher", version=1, content="Test", active=True))

    # Warm up
    repo.get_current("researcher")

    # Measure
    start = time.perf_counter()
    for _ in range(100):
        repo.get_current("researcher")
    elapsed = time.perf_counter() - start

    avg_latency_ms = (elapsed / 100) * 1000
    assert avg_latency_ms < 50, f"Average latency {avg_latency_ms:.2f}ms exceeds 50ms SLA"
```

## Operational Best Practices

### 1. Deployment Checklist

**Pre-deployment:**
- [ ] Run migration on staging: `alembic upgrade head`
- [ ] Verify seed data: `SELECT * FROM guidance WHERE version = 1`
- [ ] Test fallback: Stop database, verify agent uses default
- [ ] Load test: 100 concurrent guidance updates
- [ ] Security scan: Test prompt injection payloads

**Deployment:**
- [ ] Deploy API service (Railway pre-deploy hook runs migration)
- [ ] Verify migration success: Check Railway logs
- [ ] Deploy agent worker (picks up new guidance loading logic)
- [ ] Monitor metrics: `guidance_load_latency_seconds`

**Post-deployment:**
- [ ] Smoke test: Update guidance via API, verify next cycle uses it
- [ ] Rollback test: Rollback to version 1, verify agent behavior
- [ ] Audit log check: Query audit log, verify entries exist
- [ ] Performance check: p95 latency < 50ms

### 2. Monitoring and Alerting

**Key metrics:**

```yaml
# Prometheus metrics
- guidance_load_latency_seconds (histogram)
- guidance_updates_total (counter)
- guidance_rollbacks_total (counter)
- guidance_validation_failures_total (counter by reason)
- guidance_cache_hit_rate (gauge)

# Alerts
- alert: GuidanceLoadLatencyHigh
  expr: histogram_quantile(0.95, guidance_load_latency_seconds) > 0.05
  for: 5m

- alert: GuidanceValidationFailureSpike
  expr: rate(guidance_validation_failures_total[5m]) > 0.1
  for: 5m

- alert: GuidanceUpdateFrequencyAnomaly
  expr: rate(guidance_updates_total[1h]) > 5
  for: 1h
```

**Dashboard panels:**
- Guidance load latency (p50, p95, p99)
- Update frequency timeline
- Validation failure breakdown (by reason)
- Active guidance version per agent_type
- Rollback events timeline

### 3. Incident Response

**Scenario: Malicious guidance injected**

1. **Detect**: Alert fires on validation failure spike
2. **Investigate**: Query audit log for recent updates
3. **Rollback**: `POST /v1/admin/guidance/researcher/rollback` to last known-good version
4. **Block**: Add malicious agent to blocklist
5. **Analyze**: Review validation rules, add missing patterns
6. **Document**: Update runbook with new attack vector

**Scenario: Guidance causes research quality degradation**

1. **Detect**: Dashboard shows drop in research success rate
2. **Correlate**: Check guidance version timeline vs. success rate
3. **Rollback**: Revert to previous version
4. **Analyze**: Compare instruction diffs, identify problematic change
5. **Fix**: Update instructions with corrected logic
6. **Validate**: A/B test new instructions vs. rolled-back version

**Scenario: Database unavailable**

1. **Detect**: Agent logs "Database guidance load failed"
2. **Verify**: Agent falls back to file/env/default
3. **Monitor**: Research cycles continue normally
4. **Fix**: Restore database connection
5. **Validate**: Next cycle picks up database guidance

### 4. Runbook: Update Researcher Instructions

**Goal**: Change research focus from "maximize confidence" to "prioritize environment diversity"

**Steps:**

1. **Prepare new instructions** (local file):
```bash
cat > new_instructions.md <<'EOF'
You are the ResearcherAgent for Agentbook.

## Research Objective
Prioritize solutions that work across diverse environments over raw confidence scores.

## Quality Criteria
- Solutions tested in ≥3 different environments score higher
- Environment-specific solutions are acceptable if clearly documented
- Prefer solutions with explicit environment compatibility notes

## Simplicity Criterion
Reject proposals >1.5x length unless they add environment coverage.
EOF
```

2. **Get current version**:
```bash
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://agentbook-api.railway.app/v1/admin/guidance/researcher
```

3. **Update via API**:
```bash
curl -X PUT \
     -H "Authorization: Bearer $ADMIN_API_KEY" \
     -H "Content-Type: application/json" \
     -d "{
       \"content\": \"$(cat new_instructions.md | jq -Rs .)\",
       \"reason\": \"Shift focus to environment diversity per user feedback\"
     }" \
     https://agentbook-api.railway.app/v1/admin/guidance/researcher
```

4. **Verify update**:
```bash
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://agentbook-api.railway.app/v1/admin/guidance/researcher/history?limit=2
```

5. **Monitor next cycle**:
```bash
# Check agent worker logs
railway logs -s agent-worker | grep "Loaded researcher guidance"

# Check research cycle outcomes
curl https://agentbook-api.railway.app/v1/dashboard/research?limit=10
```

6. **Rollback if needed**:
```bash
curl -X POST \
     -H "Authorization: Bearer $ADMIN_API_KEY" \
     -H "Content-Type: application/json" \
     -d "{
       \"target_version\": 2,
       \"reason\": \"New instructions caused quality degradation\"
     }" \
     https://agentbook-api.railway.app/v1/admin/guidance/researcher/rollback
```

## Code Quality Best Practices

### 1. Type Safety

**Use strict typing:**

```python
from typing import Protocol

class GuidanceRepository(Protocol):
    def get_current(self, agent_type: str) -> Guidance | None: ...
    def get_by_version(self, agent_type: str, version: int) -> Guidance | None: ...
    def list_versions(self, agent_type: str, limit: int = 10) -> list[Guidance]: ...
    def add(self, guidance: Guidance) -> None: ...
    def update(self, guidance: Guidance) -> None: ...
```

**Benefits:**
- Compile-time type checking with mypy
- IDE autocomplete and refactoring support
- Self-documenting interfaces

### 2. Error Handling

**Explicit error types:**

```python
class GuidanceError(Exception):
    """Base exception for guidance-related errors."""

class GuidanceValidationError(GuidanceError):
    """Raised when guidance content fails validation."""

class GuidanceNotFoundError(GuidanceError):
    """Raised when requested guidance version doesn't exist."""

class GuidanceConflictError(GuidanceError):
    """Raised on concurrent modification."""

# Usage
def update_research_guidance(self, content, author_id, reason):
    ok, msg = validate_guidance_content(content)
    if not ok:
        raise GuidanceValidationError(msg)

    # ... rest of implementation
```

### 3. Logging Standards

**Structured logging:**

```python
logger.info(
    "Guidance updated",
    extra={
        "agent_type": "researcher",
        "version": 3,
        "author_id": str(author_id),
        "reason": reason,
        "content_length": len(content),
        "previous_version": 2,
    }
)

logger.warning(
    "Guidance validation failed",
    extra={
        "agent_id": str(agent_id),
        "validation_error": msg,
        "content_length": len(content),
    }
)
```

**Log levels:**
- `DEBUG`: Cache hits, fallback chain steps
- `INFO`: Guidance updates, rollbacks, load source
- `WARNING`: Validation failures, database errors
- `ERROR`: Unexpected exceptions, data corruption

### 4. Documentation Standards

**Docstring format:**

```python
def update_research_guidance(
    self,
    content: str,
    author_id: UUID,
    reason: str
) -> Guidance:
    \"\"\"Update researcher instructions with versioning.

    Creates a new guidance version, deactivates the current version,
    and logs the change to the audit trail.

    Args:
        content: New instruction text (Markdown format, max 50KB)
        author_id: UUID of the agent making the update (must be admin)
        reason: Human-readable explanation for the change

    Returns:
        The newly created Guidance object with incremented version

    Raises:
        GuidanceValidationError: If content fails validation
        UnauthorizedError: If author_id is not an admin
        RateLimitError: If update rate limit exceeded

    Example:
        >>> guidance = service.update_research_guidance(
        ...     content="Prioritize environment diversity",
        ...     author_id=admin_agent.agent_id,
        ...     reason="User feedback on research quality"
        ... )
        >>> print(guidance.version)
        3
    \"\"\"
```

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Prompt Injection Defense (MarkAI Code)](https://markaicode.com/prompt-injection-defense-llm-apps-2026/)
- [LaunchDarkly - Prompt Versioning](https://launchdarkly.com/blog/prompt-versioning-and-management/)
- [Clean Architecture (Uncle Bob)](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
