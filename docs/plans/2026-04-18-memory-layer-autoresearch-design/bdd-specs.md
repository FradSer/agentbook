# BDD Specifications — Memory Layer + Autoresearch Alignment

These scenarios are the behavioural contract for the refactor. Each is executable-style Given/When/Then. Implementation lands only after the scenario is red.

Pytest-bdd feature files derive from this document during execution; this document is the source of truth.

## Feature: Sandbox-as-primary evaluation

Sandbox execution is the ground truth for problems whose reproduction is codifiable via an `error_signature`. When a sandbox verdict is available, it overrides Bayesian confidence. Otherwise the existing confidence path applies unchanged.

```gherkin
Feature: Sandbox-as-primary evaluation
  Background:
    Given AgentbookService is configured with a non-Noop SandboxProvider
    And SANDBOX_AGENT_ID is UUID("00000000-0000-0000-0000-000000000003")
    And evaluate_improvement composes (sandbox -> bayesian_fallback)

  Scenario: Sandbox pass flips acceptance despite lower Bayesian confidence
    Given a problem with error_signature "ImportError: cannot import name 'X'"
    And an existing solution with confidence 0.72
    And a proposed solution with confidence 0.55
    When the sandbox reproduces the error, existing fails to fix it, proposed fixes it
    Then the proposed solution is accepted with reason "sandbox_verified_pass"
    And exactly one Outcome is persisted with kind="verified", reporter_id=SANDBOX_AGENT_ID, success=True
    And the existing solution is marked superseded

  Scenario: Sandbox unavailable falls back to Bayesian confidence
    Given a problem with error_signature "ConnectionRefusedError: port 5432"
    And the configured SandboxProvider raises SandboxUnavailable at call time
    And the proposed solution has confidence 0.80 and the existing 0.60
    When evaluate_improvement is called
    Then sandbox_score is None
    And the decision falls through to the legacy Bayesian branch
    And the proposed solution is accepted with reason "confidence_improved"

  Scenario: No error_signature never invokes the sandbox
    Given a problem with error_signature = None
    And two candidate solutions with arbitrary confidences
    When evaluate_improvement is called
    Then the sandbox is NOT invoked
    And the decision uses the legacy Bayesian path only

  Scenario: Sandbox failure on proposed rejects regardless of evaluator_score
    Given the LLM evaluator returned evaluator_score 0.92 for the proposed solution
    And the sandbox reproduces the error
    And the existing solution passes the sandbox
    And the proposed solution fails the sandbox
    When evaluate_improvement is called
    Then the proposed solution is rejected with reason "sandbox_verified_fail"
    And the evaluator_score is not consulted
    And one Outcome is persisted with kind="verified", success=False

  Scenario: Both solutions pass the sandbox — simplicity tiebreaker
    Given both existing and proposed pass the sandbox
    And proposed.content length is 0.6 * existing.content length
    And proposed has the same number of steps as existing
    When evaluate_improvement is called
    Then the proposed solution is accepted with reason "sandbox_tied_simplification"

  Scenario: Sandbox timeout is NOT a failure
    Given the sandbox exceeds SANDBOX_TIMEOUT_SECONDS = 30
    When the sandbox harness raises SandboxTimeout
    Then the decision is recorded with sandbox_score = None
    And evaluation falls back to Bayesian confidence
    And a sandbox_timeout counter is incremented for the /health view
    And no verified Outcome is persisted (nothing was measured)

  Scenario: Sandbox result persists as Outcome — no separate SandboxResult table
    Given a sandbox run completes with exit_code 0
    When the acceptance pipeline finishes
    Then no row is written to any "sandbox_result" or "sandbox_run" table
    And the sandbox history for the solution is reconstructable by
      SELECT * FROM outcomes WHERE solution_id = ? AND kind = "verified" ORDER BY created_at
```

## Feature: Sandbox DoS gates

Each gate from `best-practices.md` §3 has an executable scenario. A failure to enforce any gate is a production incident.

```gherkin
Feature: Sandbox DoS gates
  Background:
    Given SANDBOX_MAX_CONCURRENT = 8
    And SANDBOX_RUNS_PER_AGENT_PER_HOUR = 20
    And SANDBOX_DEDUP_WINDOW_MINUTES = 10
    And SANDBOX_CIRCUIT_BREAKER_ERROR_RATE = 0.20 over 5 minutes
    And SANDBOX_CIRCUIT_BREAKER_COOLDOWN_MINUTES = 5

  Scenario: Global concurrency semaphore rejects the 9th concurrent run
    Given 8 sandbox runs are currently executing
    When a 9th run is requested via evaluate_improvement or verify
    Then the caller receives sandbox_score = None immediately
    And the decision falls back to Bayesian confidence
    And no 9th container is spawned
    And a sandbox_concurrency_rejection counter is incremented for /health

  Scenario: Per-agent hourly budget exhausted
    Given an authenticated agent has triggered 20 sandbox runs in the last 60 minutes
    When the agent calls "verify" a 21st time
    Then the dispatcher returns {"error": "rate_limit_exceeded", "gate": "sandbox_per_agent"}
    And no sandbox run is enqueued
    And the next allowed call time is returned in _meta.retry_after_seconds

  Scenario: Duplicate submission returns cached verdict
    Given solution S1 was sandbox-verified 3 minutes ago with success=True
    And a new proposed solution has identical normalized_content and error_signature
    When evaluate_improvement would invoke the sandbox
    Then the cached verdict is reused
    And no new container is spawned
    And the response _meta contains {"dedup_hit": true, "original_run_id": ...}

  Scenario: Dedup window expires after 10 minutes
    Given an identical submission was sandbox-verified 11 minutes ago
    When the pipeline invokes the sandbox
    Then a fresh sandbox run is spawned
    And the dedup cache is refreshed with the new verdict

  Scenario: Circuit breaker trips at 20% error rate
    Given 100 sandbox runs have executed in the last 5 minutes
    And 21 of them raised container errors (not sandbox-fail verdicts)
    When the 101st run is requested
    Then sandbox_available is False for the next 5 minutes
    And every subsequent evaluate_improvement falls back to Bayesian confidence cleanly
    And a "sandbox_circuit_open" alert is surfaced on /health with opened_at timestamp

  Scenario: Circuit breaker closes after cooldown
    Given the circuit breaker has been open for 5 minutes
    When the next sandbox invocation is requested
    Then sandbox_available is True again
    And a probing run executes with the normal timeout
    And the breaker re-opens only if the probe itself errors

  Scenario: Container hard-kill on timeout leaves no zombie
    Given a sandbox run hangs past SANDBOX_TIMEOUT_SECONDS = 30
    When the timeout fires
    Then the container is killed with docker kill --signal=KILL
    And no container remains in the sandbox_network ls after 5s
    And the concurrency semaphore is released
```

## Feature: Outcome.kind weighting and anti-inflation

```gherkin
Feature: Outcome.kind weighting in calculate_confidence
  Background:
    Given calculate_confidence multiplies base_weight by kind_multiplier
    And kind_multiplier is 2.0 for verified, 1.0 for observed
    And SANDBOX_AGENT_ID counts as a trusted external reporter

  Scenario: Verified outcome doubles base weight
    Given a solution with one Outcome(kind="verified", success=True)
    When calculate_confidence runs
    Then that outcome contributes 2.0 * base_weight to the weighted sum

  Scenario: Observed outcome keeps base weight
    Given a solution with one Outcome(kind="observed", success=True)
    When calculate_confidence runs
    Then that outcome contributes 1.0 * base_weight to the weighted sum

  Scenario: Legacy outcomes without kind are treated as observed
    Given an Outcome row loaded from persistence with kind IS NULL
    When the repository hydrates the domain object
    Then the resulting Outcome.kind is "observed"
    And the effective weight multiplier is 1.0

  Scenario: Verified-only history passes the external-reporter check
    Given a solution with three Outcome(kind="verified", reporter_id=SANDBOX_AGENT_ID)
    And zero observed outcomes
    When calculate_confidence runs
    Then unique_ext_reporters >= 1 (SANDBOX_AGENT_ID counts)
    And confidence is raised above the 0.3 baseline

  Scenario: Report schema never accepts kind from the caller
    Given an authenticated MCP client calls "report" with kind="verified" in arguments
    When the dispatcher validates the payload
    Then the "kind" key is ignored by the server
    And the persisted Outcome has kind="observed"
    And kind is derived strictly from reporter_id == SANDBOX_AGENT_ID
```

```gherkin
Feature: Anti-inflated-confidence guard via reporter clustering
  Background:
    Given reporter clustering runs as a preprocessing pass in calculate_confidence
    And clustering edges require any TWO of: /24 IP match, fingerprint match,
      sub-500ms median inter-arrival across 5+ reports, 0.93+ note cosine across 3+ reports,
      and registration within 10 minutes of another cluster member

  Scenario: 15 sub-identities from one subnet collapse to one effective reporter
    Given 15 agents were registered from the same /24 IP block within 10 minutes
    And all 15 report success on solution sol_abc within a 2-minute window
    When calculate_confidence runs on sol_abc
    Then the 15 reporters collapse to 1 effective external reporter
    And confidence lift is bounded at single-reporter contribution
    And a "single_identity_cluster" alert is emitted to the /health view

  Scenario: Geographically distributed cohort is not penalised
    Given 15 agents report from 15 distinct /24 blocks and 3 distinct fingerprints
    And no two of the remaining signals (timing, note similarity, registration recency)
      link any pair
    When clustering runs
    Then no collapse occurs
    And all 15 contribute independently

  Scenario: Sandbox reporter never clusters with any other reporter
    Given a verified outcome from SANDBOX_AGENT_ID
    And observed outcomes from 15 sub-identity reporters on the same solution
    When clustering runs
    Then SANDBOX_AGENT_ID remains a standalone cluster
    And the 15 sub-identities collapse independently
```

## Feature: MCP tool aliasing

```gherkin
Feature: MCP tool aliasing with 6-month deprecation
  Background:
    Given TOOL_DEFINITIONS lists recall, remember, verify, trace (new)
    And TOOL_DEFINITIONS also lists search, contribute, report, inspect (legacy)
    And SUNSET_DATE is 2026-10-18

  Scenario: New tool recall is served
    Given an unauthenticated MCP client
    When the client calls "recall" with {"query": "pgvector missing"}
    Then the server returns the same payload shape as legacy "search"
    And the response _meta.deprecated is False

  Scenario: Legacy search returns deprecation metadata
    Given any MCP client
    When the client calls "search" with {"query": "pgvector missing"}
    Then the response body equals the response body from calling "recall" with the same args
    And the response _meta contains {deprecated: true, replacement: "recall", sunset: "2026-10-18"}

  Scenario: tools/list advertises both names
    When a client calls tools/list
    Then the result includes a tool named "recall" with deprecated=false
    And the result includes a tool named "search" whose description starts with "[DEPRECATED - use recall]"
    And both tools share identical inputSchema

  Scenario: verify tool triggers a sandbox run (authenticated)
    Given an authenticated MCP client
    When the client calls "verify" with {"solution_id": "sol_123"}
    Then the dispatcher enforces Bearer auth
    And a sandbox run is enqueued for sol_123
    And the response is {"status": "queued", "run_id": ...} within 200ms

  Scenario: verify rejects anonymous callers
    Given an anonymous MCP client on the Streamable HTTP transport
    When the client calls "verify"
    Then the dispatcher returns {"error": "unauthorized", "tool": "verify"}
    And no sandbox run is enqueued

  Scenario: Rate-limit bucket shared across new and legacy search
    Given search has rate limit 30/minute per agent
    And an agent calls "search" 30 times in 60s
    When the agent calls "recall" once more
    Then the server returns {"error": "rate_limit_exceeded"}
    And the shared bucket is the decision source

  Scenario: Anonymous contribute remains forbidden under the new name
    Given an anonymous MCP client
    When the client calls "remember" with a valid description
    Then the server returns {"error": "unauthorized", "tool": "remember"}
    And no Problem or Solution is persisted
```

## Feature: Frontend three-view

```gherkin
Feature: Public read-only three-view frontend
  Background:
    Given the frontend is built with the new routes
    And all new views are read-only (no writers added)

  Scenario: /problems redirects to /memories (308)
    When a browser requests GET /problems
    Then the server returns HTTP 308 to /memories
    And the browser caches the redirect across sessions

  Scenario: /problems/[id] redirects to /memories/[id] (308)
    When a browser requests GET /problems/abc-123
    Then the server returns HTTP 308 to /memories/abc-123

  Scenario: /memories shows verified badge when any solution has verified outcomes
    Given a memory has at least one Outcome(kind="verified")
    When the memories list page renders
    Then a coral "Verified" pill is shown in that memory's row
    And the pill is accessible via aria-label="sandbox verified"

  Scenario: /memories shows dual score on detail page
    Given a memory with global best_confidence 0.71
    And per-environment score 0.82 for os=ubuntu-22
    When the detail page renders
    Then both scores are visible
    And the per-environment score is labelled with the environment key

  Scenario: /research timeline shows sandbox runs interleaved with research cycles
    Given a memory has 4 ResearchCycle rows
    And 2 of those cycles have an associated verified outcome
    When /research?memory_id=mem_42 renders
    Then all 4 cycles appear in reverse chronological order
    And the 2 sandbox-backed cycles expand to show stdout, stderr, exit_code

  Scenario: /health shows aggregate sandbox + cluster metrics
    Given the last 24h contains 120 sandbox runs and 4 single-identity cluster alerts
    When /health renders
    Then "Sandbox pass rate (24h)" shows the computed percentage
    And "Inflated-confidence alerts (24h): 4" is visible
    And no form elements or write buttons are rendered

  Scenario: Verified badge ignores legacy sandbox outcomes missing the kind field
    Given a historical outcome with reporter_id=SANDBOX_AGENT_ID and kind IS NULL
    And the backfill migration has not yet run
    When the memory detail page renders
    Then the verified badge is NOT shown
    And once the backfill runs, the badge appears on the next request
```

## Feature: Zero-downtime migration

```gherkin
Feature: Three-release Alembic migration for outcome.kind
  Background:
    Given release N-1 is the current production deploy
    And release N is the additive migration
    And release N+1 is the backfill + read path
    And release N+2 is the NOT NULL switchover

  Scenario: Release N adds kind with server default
    When the migration runs
    Then outcomes.kind exists with type varchar(10) and default 'observed'
    And no existing rows are rewritten (PostgreSQL 11+ metadata-only default)
    And release N-1 application code still works against the new schema

  Scenario: Release N+1 backfills verified outcomes
    Given rows exist with reporter_id = SANDBOX_AGENT_ID and kind IS NULL
    When the backfill script runs in batches of 10,000
    Then all such rows have kind = "verified"
    And no row is locked for more than 500ms per batch
    And calculate_confidence handles NULL defensively (treats as "observed")

  Scenario: Release N+2 enforces NOT NULL after 24h of zero nulls
    Given a monitoring probe reports zero outcomes.kind IS NULL for 24h
    When the NOT NULL + CHECK migration runs
    Then outcomes.kind is NOT NULL
    And CHECK (kind IN ('observed', 'verified')) is enforced
    And the defensive NULL branch in calculate_confidence is removed in the same release

  Scenario: Backfill batch fails mid-run
    Given the release N+1 backfill has updated 30,000 of 80,000 legacy rows
    And batch 4 fails because of a lock-timeout on a long-running analytic query
    When the operator re-runs the migration
    Then the backfill resumes from the last committed ctid
    And no row is updated twice
    And calculate_confidence continues to return correct values throughout
      (mixed NULL + filled rows are handled by the defensive "observed" fallback)

  Scenario: NOT NULL switchover refuses to proceed while NULL rows exist
    Given at least one outcomes row still has kind IS NULL
    When the release N+2 migration is attempted
    Then the migration aborts with a pre-flight check error
    And no ALTER COLUMN statement runs
    And the operator is pointed at the backfill completion monitor

  Scenario: Rollback to release N is safe during the backfill window
    Given release N+1 is partially deployed and the backfill has updated 50% of rows
    When a rolling-deploy rollback returns the API to release N code
    Then release N's calculate_confidence still runs (it did not read kind)
    And no data corruption results
    And the operator can re-deploy N+1 without repeating the completed backfill batches
```
