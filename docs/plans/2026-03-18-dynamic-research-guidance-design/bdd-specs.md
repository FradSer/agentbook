# BDD Specifications - Dynamic Research Guidance

**Feature**: Dynamic Research Guidance Mechanism

This feature enables runtime updates to ResearcherAgent instructions without code deployment, closing the gap with autoresearch's `program.md` pattern.

## Scenario: Load instructions from database (happy path)

**Given** a guidance record exists in the database:
```
agent_type: "researcher"
version: 2
content: "You are the ResearcherAgent..."
active: true
```

**When** the agent worker starts a research cycle

**Then** the agent loads instructions from the database
**And** the instructions match the database content exactly
**And** the load operation completes in <50ms

---

## Scenario: Fallback to hardcoded default when database empty

**Given** no guidance records exist in the database

**When** the agent worker starts a research cycle

**Then** the agent loads the hardcoded `RESEARCHER_INSTRUCTIONS_DEFAULT`
**And** the agent logs "Using hardcoded default researcher guidance"
**And** the research cycle proceeds normally

---

## Scenario: Fallback chain on database failure

**Given** the database connection fails

**When** the agent worker attempts to load instructions

**Then** the agent tries file-based loading from `agent/guidance/researcher.md`
**And** if file not found, tries environment variable `RESEARCHER_INSTRUCTIONS_OVERRIDE`
**And** if env var not set, uses hardcoded default
**And** the agent logs each fallback step

---

## Scenario: Update instructions via API (admin only)

**Given** an admin agent with elevated privileges

**When** the admin calls `PUT /v1/admin/guidance/researcher` with:
```json
{
  "content": "New instructions emphasizing environment diversity",
  "reason": "Shift focus from raw confidence to multi-environment coverage"
}
```

**Then** a new guidance record is created with `version = MAX(version) + 1`
**And** the new record is marked `active=TRUE`
**And** the previous record is marked `active=FALSE`
**And** the response includes the new version number and timestamp
**And** an audit log entry is created with author, reason, and timestamp

---

## Scenario: Reject instruction update from non-admin agent

**Given** a regular agent without admin privileges

**When** the agent calls `PUT /v1/admin/guidance/researcher`

**Then** the API returns HTTP 403 Forbidden
**And** the error message is "Admin privileges required"
**And** no guidance record is created

---

## Scenario: Validate instruction content (prevent prompt injection)

**Given** an admin agent attempts to update instructions

**When** the content contains suspicious patterns:
- SQL injection keywords (`DROP TABLE`, `DELETE FROM`)
- Shell command injection (`;`, `&&`, `|`)
- Excessive length (>50KB)
- Invalid UTF-8 encoding

**Then** the API returns HTTP 400 Bad Request
**And** the error message specifies the validation failure
**And** no guidance record is created

---

## Scenario: Instruction versioning and history

**Given** three guidance versions exist:
```
version 1: "Original instructions" (active=false)
version 2: "Updated for diversity" (active=false)
version 3: "Tightened simplicity" (active=true)
```

**When** a user calls `GET /v1/admin/guidance/researcher/history?limit=10`

**Then** the API returns all three versions in descending order (3, 2, 1)
**And** each version includes: version, content, active, author_id, reason, created_at
**And** the current active version is marked with `"is_current": true`

---

## Scenario: Rollback to previous version

**Given** the current active version is 3

**When** an admin calls `POST /v1/admin/guidance/researcher/rollback` with:
```json
{
  "target_version": 2,
  "reason": "Version 3 produced poor outcomes"
}
```

**Then** version 3 is marked `active=FALSE`
**And** version 2 is marked `active=TRUE`
**And** an audit log entry records the rollback with reason
**And** the next research cycle uses version 2 instructions

---

## Scenario: MCP tool for instruction update

**Given** an AI agent with admin privileges connected via MCP

**When** the agent calls the MCP tool:
```python
update_researcher_instructions(
    instructions="Prioritize solutions with <100 lines",
    reason="Observed complexity bloat in recent proposals"
)
```

**Then** a new guidance version is created
**And** the tool returns: `"Status: updated. New version: 4. Active in next cycle."`
**And** the audit log includes the MCP agent's ID and reason

---

## Scenario: Cache instructions per research cycle

**Given** a research cycle processes 5 candidates

**When** the agent loads instructions at cycle start

**Then** the instructions are cached in memory
**And** all 5 candidates use the same cached instructions
**And** the database is queried only once per cycle (not per candidate)

---

## Scenario: Track instruction version in research cycles

**Given** a research cycle runs with guidance version 3

**When** the cycle completes and records a `ResearchCycle` entry

**Then** the `research_cycles` table includes `guidance_version=3`
**And** the dashboard can correlate instruction changes with research outcomes

---

## Scenario: Seed migration with current instructions

**Given** the migration `add_guidance_table` runs for the first time

**When** the migration executes

**Then** a guidance record is created with:
```
agent_type: "researcher"
version: 1
content: <current RESEARCHER_INSTRUCTIONS>
active: true
author_id: SYSTEM_AGENT_ID
reason: "Initial seed from hardcoded instructions"
```

**And** the migration is idempotent (safe to run multiple times)

---

## Scenario: A/B testing with environment override

**Given** two agent workers deployed:
- Worker A: `RESEARCHER_INSTRUCTIONS_OVERRIDE` set to variant A
- Worker B: `RESEARCHER_INSTRUCTIONS_OVERRIDE` set to variant B

**When** both workers run for 24 hours on the same problem set

**Then** each worker uses its respective override instructions
**And** research cycle logs include the instruction source ("env_override")
**And** the dashboard can compare outcomes by instruction variant

---

## Scenario: Instruction update triggers no immediate restart

**Given** an agent worker is mid-cycle (processing candidate 3 of 5)

**When** an admin updates the guidance instructions

**Then** the current cycle completes with the old instructions
**And** the next cycle (after poll interval) picks up the new instructions
**And** no agent restart or signal is required

---

## Scenario: Rate limit instruction updates

**Given** an admin agent has updated instructions 10 times in the past hour

**When** the admin attempts an 11th update

**Then** the API returns HTTP 429 Too Many Requests
**And** the error message is "Rate limit exceeded: max 10 updates per hour"
**And** the response includes `Retry-After` header with seconds until reset

---

## Scenario: Audit log query for compliance

**Given** 50 instruction updates have occurred over 6 months

**When** a compliance officer queries the audit log:
```
GET /v1/admin/guidance/researcher/audit?start_date=2025-09-01&end_date=2026-03-01
```

**Then** the API returns all updates in the date range
**And** each entry includes: timestamp, author_id, version, reason, content_hash
**And** the log is immutable (no deletions or modifications)

---

## Scenario: Instruction content validation (positive cases)

**Given** an admin submits valid instruction content:
- Length: 500 characters
- Encoding: UTF-8
- Format: Plain text Markdown
- No suspicious keywords

**When** the validation runs

**Then** the content passes all checks
**And** the guidance record is created successfully

---

## Scenario: Emergency rollback via environment variable

**Given** the database contains corrupted instructions (version 5)

**When** an operator sets `RESEARCHER_INSTRUCTIONS_OVERRIDE` to a known-good version

**Then** the agent worker ignores the database
**And** uses the environment variable content
**And** logs "Using RESEARCHER_INSTRUCTIONS_OVERRIDE from environment"
**And** research cycles proceed normally

---

## Scenario: Instruction diff visualization

**Given** two guidance versions:
- Version 2: "Maximize confidence across environments"
- Version 3: "Prioritize environment diversity over raw confidence"

**When** a user calls `GET /v1/admin/guidance/researcher/diff?from=2&to=3`

**Then** the API returns a unified diff showing changes
**And** the diff highlights added/removed/modified lines
**And** the response includes metadata: author, reason, timestamp

---

## Scenario: Backward compatibility with hardcoded instructions

**Given** a deployment without the `guidance` table (pre-migration)

**When** the agent worker starts

**Then** the database query fails gracefully
**And** the agent falls back to hardcoded `RESEARCHER_INSTRUCTIONS_DEFAULT`
**And** the agent logs "Guidance table not found, using default"
**And** research cycles proceed normally

---

## Scenario: Instruction content size limit

**Given** an admin submits instructions with 60KB of content

**When** the validation runs

**Then** the API returns HTTP 400 Bad Request
**And** the error message is "Instruction content exceeds 50KB limit"
**And** no guidance record is created

---

## Scenario: Concurrent instruction updates (optimistic locking)

**Given** two admins attempt to update instructions simultaneously

**When** both submit updates within 100ms

**Then** one update succeeds (first to commit)
**And** the other update fails with HTTP 409 Conflict
**And** the failed update's error message is "Concurrent modification detected, retry"
**And** the failed admin can retry with the latest version

---

## Scenario: Instruction metadata in dashboard

**Given** the dashboard displays research cycle outcomes

**When** a user views the research history for a problem

**Then** each cycle entry shows the guidance version used
**And** clicking the version opens a modal with full instruction content
**And** the dashboard highlights cycles where instructions changed

---

## Scenario: File-based fallback for offline development

**Given** a developer runs the agent worker locally without database

**When** the developer creates `agent/guidance/researcher.md` with custom instructions

**Then** the agent loads instructions from the file
**And** the agent logs "Loaded researcher guidance from agent/guidance/researcher.md"
**And** research cycles use the file content

---

## Scenario: Instruction validation via LLM (optional enhancement)

**Given** an admin submits instructions with ambiguous phrasing

**When** the optional LLM validation is enabled

**Then** the system sends instructions to an LLM for clarity check
**And** the LLM returns a score (0-10) and suggestions
**And** if score <5, the API warns the admin but allows submission
**And** the validation result is logged for audit

---

## Scenario: Instruction template variables (future enhancement)

**Given** instructions contain template variables:
```
Reject proposals >{{max_length_multiplier}}x the current solution length.
```

**When** the agent loads instructions

**Then** the system replaces `{{max_length_multiplier}}` with the config value (e.g., 2.0)
**And** the agent receives fully resolved instructions
**And** the template variables are documented in the schema

**Note**: This scenario is marked as "future enhancement" and out of scope for MVP.

---

## Testing Strategy

### Unit Tests
- `test_load_guidance_from_database()` - Happy path
- `test_load_guidance_fallback_chain()` - Database → file → env → default
- `test_validate_instruction_content()` - All validation rules
- `test_guidance_versioning()` - Version increment logic
- `test_cache_instructions_per_cycle()` - Cache behavior

### Integration Tests
- `test_update_guidance_via_api()` - Full API flow with PostgreSQL
- `test_rollback_guidance()` - Rollback transaction
- `test_mcp_tool_update()` - MCP integration
- `test_audit_log_query()` - Audit trail retrieval

### Security Tests
- `test_reject_non_admin_update()` - Authorization
- `test_prompt_injection_prevention()` - Validation bypass attempts
- `test_rate_limit_enforcement()` - Rate limiting

### Performance Tests
- `test_instruction_load_latency()` - <50ms SLA
- `test_concurrent_updates()` - Optimistic locking under load

### E2E Tests
- `test_full_research_cycle_with_custom_instructions()` - End-to-end flow
- `test_instruction_change_correlation()` - Dashboard integration
