# Task 004b (impl): MCP recall query-event recording

**depends-on**: ["004a"]

## Description

Enrich the MCP `recall` path so it passes caller identity into the service's recording hook. Make Task 004a's tests pass.

## Execution Context

- **Layer:** presentation/MCP (`backend/presentation/mcp/tools.py`). Presentation passes context into the service; it never touches a repo directly.
- **Type:** impl (Green).
- **Prereqs:** 004a.

## BDD Scenario

```gherkin
Scenario: An authenticated recall records an identity-enriched query event
  Given an MCP server whose service has a query_events repository
  And an authenticated agent in the recall context
  When recall is dispatched with a query that matches a problem
  Then a QueryEvent is recorded with agent_id and ip_hash from the agent context
  And the recall response is unchanged

Scenario: An anonymous recall still records a dedup-capable event
  Given an MCP recall with no authenticated agent but a remote address
  When recall is dispatched
  Then a QueryEvent is recorded with agent_id None and ip_hash derived from the remote address
  And recurrence dedup can still collapse repeated anonymous queries from one address
```

## Files to Modify/Create

- `backend/presentation/mcp/tools.py` — in the `recall` handler of `dispatch_tool` (~lines 532-564), pass caller context into the search.

## Steps

1. The `recall` handler already reads `agent = _current_agent_ctx.get(None)` and `remote_addr = _current_remote_addr_ctx.get(None)` for rate-limiting. Reuse them to build the `CallerContext` introduced in 003b. **Intent only:**

   ```python
   # Intent only — wiring sketch, not final
   ctx = CallerContext(
       agent_id=agent.agent_id if agent else None,
       ip_hash=agent.ip_hash if agent else hash_remote_addr(remote_addr),
       fingerprint_hash=agent.fingerprint_hash if agent else None,
   )
   search_response = service.search_problems(..., caller=ctx)
   ```

2. For the anonymous `ip_hash`, reuse the existing remote-address hashing used elsewhere for identity (match the `ip_hash` derivation already applied to agents in `clustering`/auth; do not invent a new hash). If no shared helper exists, add a single `hash_remote_addr(addr: str | None) -> str | None` in the MCP layer and use it consistently.
3. Do **not** record the event in the presentation layer directly — only pass `caller` into the service; the service records (preserves the Clean Architecture dependency rule).
4. Keep the response construction unchanged.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_mcp_recall_recurrence.py -q
make fast
```

## Success Criteria

- Task 004a tests pass **GREEN**; `make fast` clean.
- `recall` response is unchanged; recording is side-channel and best-effort.
- Optional live smoke: run a `recall` (see `docs/mcp-setup.md`), then `GET /v1/dashboard/recurrence-density` reflects it.
