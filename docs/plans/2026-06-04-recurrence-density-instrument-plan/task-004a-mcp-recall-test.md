# Task 004a (test): MCP recall query-event recording

**depends-on**: ["003b"]

## Description

Failing tests that the MCP `recall` path records a query event enriched with caller identity (`agent_id`, `ip_hash`, `fingerprint_hash`) for authenticated callers and a usable identity for anonymous callers (`ip_hash` from remote addr), so dedup and organic-recurrence work on real MCP traffic.

## Execution Context

- **Layer:** unit test (`backend/tests/unit/`), drives `dispatch_tool` directly with MCP context vars set.
- **Type:** test (Red).
- **Prereqs:** 003b (the service recording hook + `CallerContext` carrier).

## BDD Scenario

(Identity-enrichment is an engineering constraint from this plan's `_index.md` — dedup-capable identity on the read path — not a design-Feature scenario.)

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

- `backend/tests/unit/test_mcp_recall_recurrence.py` — new unit test file (or extend the existing MCP tools test module if one exists).

## Steps

1. Dispatch `recall` with an authenticated agent set in `current_agent` context → assert one `QueryEvent` recorded with that `agent_id` and `ip_hash`.
2. Dispatch `recall` anonymously with `current_remote_addr` set → event recorded with `agent_id=None`, `ip_hash` derived from the remote address.
3. Assert the `recall` JSON response is byte-for-byte the same as before the hook (recording is side-channel).
4. Recording failure does not break `recall` (best-effort, mirrors Task 003).

Set `current_agent` / `current_remote_addr` context vars as the existing MCP tests do.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_mcp_recall_recurrence.py -q
```

## Success Criteria

- Tests **fail RED** for the right reason: the recall handler does not yet record events / does not pass caller context.
- Both authenticated and anonymous identity paths are asserted.
