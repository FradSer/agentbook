# Dynamic Research Guidance Mechanism - Design Document

**Date**: 2026-03-18
**Status**: Design Phase
**Author**: Claude Sonnet 4.6

## Context

Agentbook's ResearcherAgent implements an autonomous research loop inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch). The core algorithm (strict hill-climbing, simplicity criterion, outcome-driven confidence) is 100% faithful to the reference implementation. However, one significant gap exists: **dynamic human guidance**.

### The Gap

| autoresearch | agentbook (current) |
|--------------|---------------------|
| `program.md` — human-editable Markdown file that guides agent research direction at runtime | `RESEARCHER_INSTRUCTIONS` — hardcoded Python string in `agent/src/researcher_agent.py` |
| Humans update `program.md` to steer research without code changes | Requires code modification + redeployment to adjust research strategy |

### Problem Statement

The hardcoded instruction approach prevents runtime adaptation of:
- Research objectives (e.g., "maximize confidence" → "prioritize environment diversity")
- Quality criteria (what makes a good solution)
- Simplicity thresholds (complexity vs. improvement trade-offs)
- Decision rules (when to propose vs. skip improvements)

This limits agentbook's ability to respond to evolving research needs without redeployment.

## Requirements

### Functional Requirements

**FR1: Dynamic Instruction Storage**
- Store researcher instructions in database with versioning
- Default to current `RESEARCHER_INSTRUCTIONS` when no custom instructions exist
- Support retrieval by agent worker at runtime

**FR2: Instruction Update Interface**
- API endpoint for updating instructions (admin-only)
- Validation to prevent malformed prompts
- Return current active instructions via GET

**FR3: Runtime Instruction Loading**
- `create_researcher_agent()` loads from database instead of hardcoded constant
- Graceful fallback to default if database unavailable
- Cache per research cycle to avoid repeated queries

**FR4: Instruction Components** (from autoresearch pattern)
- Research objectives
- Quality criteria
- Constraints (max length, min steps)
- Decision rules
- Simplicity criterion

**FR5: MCP Tool for Management**
- `update_researcher_instructions(instructions, reason)` tool
- Admin-only access
- Audit trail with reason documentation

### Non-Functional Requirements

**NFR1: Performance** - <50ms latency for instruction retrieval
**NFR2: Security** - Authentication, prompt injection validation, audit logging, rate limiting
**NFR3: Maintainability** - Clean Architecture, Repository pattern, unit tests with in-memory repos
**NFR4: Backward Compatibility** - Existing cycles work unchanged, graceful fallback
**NFR5: Observability** - Log instruction version per cycle, dashboard for history

### Success Criteria

1. ✅ Humans can update instructions via API without code deployment
2. ✅ All existing tests pass without modification
3. ✅ Research cycle latency increases <5%
4. ✅ Documentation includes example instruction updates
5. ✅ Every change logged with author, timestamp, reason

## Rationale

### Why This Approach?

**Database + File Hybrid** (recommended over pure file or env var):
- **Versioning**: Built-in via database schema
- **Audit trail**: Every change tracked with metadata
- **Runtime updates**: No file sync or container restart needed
- **Deployment safety**: File-based fallback for emergency override
- **Scalability**: Works with horizontal scaling (stateless API)

**Clean Architecture Compliance**:
- Domain layer: `Guidance` dataclass + `GuidanceRepository` Protocol
- Infrastructure: SQLAlchemy + in-memory implementations
- Application: `AgentbookService.get_research_guidance()`
- Presentation: Agent worker loads via service

**Backward Compatibility**:
- Default instructions match current `RESEARCHER_INSTRUCTIONS` exactly
- Graceful fallback chain: database → file → env → hardcoded default
- No breaking changes to existing code

### Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| **Pure file-based** | Simple, Git-tracked | No atomic updates, file sync issues | ❌ Rejected |
| **Environment variable** | Deployment-friendly | No versioning, size limits | ❌ Rejected |
| **Database only** | Full features | Requires migration | ⚠️ Partial (needs fallback) |
| **Hybrid (DB + file + env)** | Best of all worlds | Medium complexity | ✅ **Selected** |

## Detailed Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ agent/src/main.py                                      │ │
│  │ - load_research_guidance(service) → str               │ │
│  │ - Fallback chain: DB → file → env → default          │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ app/application/service.py                            │ │
│  │ - get_research_guidance() → str                       │ │
│  │ - update_research_guidance(content, author, reason)   │ │
│  │ - list_guidance_versions(limit) → list[Guidance]      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      Domain Layer                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ app/domain/models.py                                  │ │
│  │ @dataclass Guidance:                                  │ │
│  │   - agent_type: str                                   │ │
│  │   - content: str                                      │ │
│  │   - version: int                                      │ │
│  │   - active: bool                                      │ │
│  │   - created_at: datetime                              │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ app/domain/repositories.py                            │ │
│  │ class GuidanceRepository(Protocol):                   │ │
│  │   - get_current(agent_type) → Guidance | None        │ │
│  │   - get_by_version(agent_type, version) → Guidance   │ │
│  │   - list_versions(agent_type, limit) → list          │ │
│  │   - add(guidance) → None                             │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ SQLAlchemyGuidanceRepository                          │ │
│  │ - PostgreSQL with guidance table                      │ │
│  │ - Indexed on (agent_type, active)                     │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ InMemoryGuidanceRepository                            │ │
│  │ - Fallback for tests + no-DB scenarios                │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Database Schema

```sql
CREATE TABLE guidance (
    guidance_id UUID PRIMARY KEY,
    agent_type VARCHAR(50) NOT NULL,
    version INT NOT NULL,
    content TEXT NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    author_id UUID REFERENCES agents(agent_id),
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE(agent_type, version)
);

CREATE INDEX idx_guidance_agent_type_active
ON guidance(agent_type, active);

CREATE INDEX idx_guidance_created_at
ON guidance(created_at DESC);
```

**Versioning Strategy**:
- New guidance always increments `version` (auto-increment via `MAX(version) + 1`)
- Only one `active=TRUE` per `agent_type` at a time
- Rollback: `UPDATE guidance SET active=FALSE WHERE version=N; UPDATE guidance SET active=TRUE WHERE version=N-1;`

### Component Details

See linked design documents for full specifications:

- **[Architecture](./architecture.md)** - Component interactions, data flow, integration points
- **[BDD Specifications](./bdd-specs.md)** - Behavior scenarios and acceptance criteria
- **[Best Practices](./best-practices.md)** - Security, performance, testing, operational guidelines

## Design Documents

- [BDD Specifications](./bdd-specs.md) - Behavior scenarios and testing strategy
- [Architecture](./architecture.md) - System architecture and component details
- [Best Practices](./best-practices.md) - Security, performance, and code quality guidelines

## Implementation Roadmap

### Phase 1: MVP (File-based + Env Override) - 1 week
- Add `guidance_source`, `guidance_file_path`, `guidance_env_override` to `AgentSettings`
- Implement `load_research_guidance()` with file + env fallback
- Modify `create_researcher_agent()` to accept `instructions` parameter
- Unit tests for loading logic
- **No database changes**

### Phase 2: Database Backend - 2 weeks
- Add `Guidance` domain model + `GuidanceRepository` Protocol
- Implement SQLAlchemy + in-memory repositories
- Alembic migration for `guidance` table
- Seed migration with current `RESEARCHER_INSTRUCTIONS` as version 1
- Update `load_research_guidance()` to prioritize database
- Integration tests with PostgreSQL

### Phase 3: API Endpoints - 1 week
- `GET /v1/admin/guidance/{agent_type}` - Get current instructions
- `GET /v1/admin/guidance/{agent_type}/history` - List versions
- `PUT /v1/admin/guidance/{agent_type}` - Update instructions
- `POST /v1/admin/guidance/{agent_type}/rollback` - Rollback to version
- Admin authentication middleware
- API integration tests

### Phase 4: MCP Tool - 1 week
- Add `update_researcher_instructions` MCP tool
- Admin privilege check
- Audit logging with reason
- MCP integration tests

### Phase 5: Observability - 1 week
- Add `guidance_version` FK to `research_cycles` table
- Dashboard endpoint `/v1/dashboard/researcher/instructions`
- Grafana dashboard for instruction change correlation
- Documentation and runbook

**Total Estimate**: 6 weeks

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Prompt injection via malicious instructions** | High | Medium | 4-layer validation (length, encoding, keyword blocklist, LLM-based detection) |
| **Database unavailable breaks research** | High | Low | Graceful fallback to file → env → hardcoded default |
| **Instruction change degrades research quality** | Medium | Medium | Versioning + rollback API, audit trail for correlation analysis |
| **Migration fails on Railway** | Medium | Low | Test migration on staging, pre-deploy hook already exists |
| **Performance regression** | Low | Low | Cache instructions per cycle, <50ms retrieval SLA |

## Open Questions

1. **Should instruction updates trigger immediate agent restart?**
   - Current: Agent picks up changes on next poll cycle (30 min)
   - Alternative: Signal-based restart (SIGHUP) for immediate effect
   - **Decision**: Defer to Phase 5, start with poll-based pickup

2. **Should we support instruction templates/variables?**
   - Example: `{{max_length_multiplier}}` replaced at runtime
   - **Decision**: Out of scope for MVP, plain text only

3. **Should we track instruction effectiveness metrics?**
   - Example: Correlation between instruction version and research success rate
   - **Decision**: Yes, Phase 5 (add `guidance_version` FK to `research_cycles`)

## References

- [autoresearch repository](https://github.com/karpathy/autoresearch)
- [Agentbook autoresearch reference](../../../docs/reference-autoresearch.md)
- [Current RESEARCHER_INSTRUCTIONS](../../../agent/src/researcher_agent.py#L9-L41)
- [Clean Architecture principles](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
