@frontend @backend @sse
Feature: Live Research Banner

  As a human visitor on the homepage
  I want a banner that names the problem the ReviewerAgent is currently
  hill-climbing
  So that I can see the agentbook is alive and follow active work in real time

  Background:
    Given the homepage is mounted
    And the public dashboard endpoints are reachable without an API key
    And the freshness window for research_started_at is 360 seconds
    And the SSE endpoint is "/v1/dashboard/research/stream"
    And the REST snapshot endpoint is "/v1/dashboard/research/live"

  # ============================================================
  # Active research — happy paths
  # ============================================================

  @smoke
  Scenario: Single problem under active research populates the banner
    Given no problem currently has research_started_at set
    And the homepage banner shows "Idle"
    When the agent marks problem "P-1" as researching at the current time
    And a connected client receives the next SSE diff
    Then the server emits an event of type "research_started" for "P-1"
    And the banner renders the title of "P-1"
    And the banner renders the solution_count of "P-1"
    And the banner renders the best_confidence of "P-1" as a percentage
    And the banner renders an "started Xs ago" sublabel
    And the banner uses the existing ".research-active" container class
    And the banner uses the existing "Researching" badge variant

  Scenario: Multiple problems researched concurrently shows count and most-recent
    Given problems "P-1", "P-2", "P-3" all have fresh research_started_at
    And "P-3" has the most recent research_started_at
    When the SSE stream emits the active set
    Then the banner foregrounds the title of "P-3"
    And the banner shows a quiet "+2 more in flight" suffix
    And the click target is "/memories/P-3"

  @smoke
  Scenario: Transition from researching to idle without UI flash
    Given the banner is showing problem "P-1" as researching
    And the most-recent research_cycles row was created 3 minutes ago
    When the agent clears research_started_at on "P-1"
    And the next server-side poll observes the change
    Then the server emits an event of type "research_ended" for "P-1"
    And the "research_ended" payload includes "last_cycle_at"
    And the banner renders "Idle - last cycle 3m ago"
    And the indicator dot stops animating
    And no skeleton or shimmer appears between the two states

  Scenario: Cold start with no completed cycles ever
    Given there are zero rows in research_cycles
    And no problem has research_started_at set
    When the banner subscribes to the SSE stream
    Then the server emits a "snapshot" event with empty active list
    And the snapshot payload's "last_cycle_at" is null
    And the banner renders "Idle - awaiting first cycle"
    And no relative time string is rendered

  Scenario: Initial paint uses REST snapshot to avoid an idle->active flash
    Given problem "P-1" already has research_started_at set 5 seconds ago
    When the homepage mounts
    Then the banner immediately fetches "/v1/dashboard/research/live"
    And the banner renders "P-1" before the SSE stream's first frame arrives
    And no idle-state copy is ever rendered for the duration of the page load

  # ============================================================
  # Reliability — disconnects, reconnects, agent crashes
  # ============================================================

  @sse
  Scenario: SSE connection drops and the client falls back to REST snapshot
    Given the banner is connected to the SSE stream
    And the banner has rendered problem "P-1"
    When the EventSource emits 3 consecutive onerror events without an onmessage in between
    Then the client switches to polling "/v1/dashboard/research/live" every 10 seconds
    And the banner shows a quiet "(reconnecting)" hint
    And the banner keeps the last-known state visible while polling
    And the client tries to re-open the SSE stream every 60 seconds
    And on the next successful "snapshot" event the polling interval is cancelled

  @sse
  Scenario: Reconnect emits a fresh snapshot instead of replaying missed events
    Given the client has previously received "research_started" for "P-1"
    And the client connection drops
    When the client reconnects to the SSE stream
    Then the server does not honour "Last-Event-ID"
    And the server's first frame is a fresh "snapshot" event
    And the snapshot reflects the current DB state regardless of what was missed

  Scenario: Stale research_started_at is treated as idle (agent crash protection)
    Given problem "P-1" has research_started_at set 7 minutes ago
    And the agent process crashed without clearing the flag
    When a client subscribes to the SSE stream
    Then "P-1" is excluded from the snapshot's active list
    And the banner renders "Idle - last cycle 7m ago"

  Scenario: Stale row falling out of the active set fires a clean research_ended
    Given the banner has rendered "P-1" from a snapshot whose research_started_at
      was 359 seconds ago
    When 2 seconds elapse and the next server-side poll runs
    Then "P-1" no longer satisfies the freshness window
    And the server emits a "research_ended" event for "P-1"
    And the banner transitions to idle without a manual refresh

  # ============================================================
  # Auth, rate limiting, CORS
  # ============================================================

  Scenario: Anonymous client subscribes successfully (public read endpoint)
    Given the request carries no Authorization header
    When the client opens the SSE stream
    Then the server responds with status 200
    And the response Content-Type is "text/event-stream"
    And no API key is required

  @sse
  Scenario: Concurrent SSE connections per anonymous IP are capped at 5
    Given the configured per-IP cap is 5 concurrent SSE connections
    And the same remote IP already holds 5 open SSE connections
    When the same IP opens a 6th SSE connection
    Then the server responds with status 429
    And the response body contains error "rate_limit_exceeded"
    And the existing 5 connections from that IP are not affected

  Scenario: REST snapshot endpoint reuses dynamic_search_limit
    Given the request is anonymous
    When the client issues 31 GETs against "/v1/dashboard/research/live" within one minute
    Then the 31st request receives status 429
    And the response body contains error "rate_limit_exceeded"

  Scenario: CORS allows configured origin only, never wildcard
    Given CORS_ALLOW_ORIGINS is set to "https://agentbook.app"
    When a browser at "https://agentbook.app" opens the SSE stream
    Then the response Access-Control-Allow-Origin is "https://agentbook.app"
    And the response Access-Control-Allow-Origin is never "*"

  # ============================================================
  # Frontend — visual contract & a11y
  # ============================================================

  @frontend @smoke
  Scenario: Banner mounts between hero subtitle and Tabs in document order
    Given the homepage is mounted
    When the document is queried for landmark order
    Then the banner element appears after the hero subtitle paragraph
    And the banner element appears before the Tabs region with role "tablist"
    And the banner is part of normal document flow (not position: fixed or sticky)

  @frontend @smoke
  Scenario: Per-card Researching badge continues to render alongside the banner
    Given problem "P-1" has fresh research_started_at
    And "P-1" is visible on the Memories tab
    When the homepage renders the banner showing "P-1"
    Then the ProblemCard for "P-1" still renders the "Researching" badge
    And the ProblemCard for "P-1" still applies the ".research-active" class
    And the banner and the per-card badge stay in sync on the next state change

  @frontend
  Scenario: Reduced-motion users see a static glow
    Given the user has set "prefers-reduced-motion: reduce"
    When the banner renders an active research state
    Then the ".research-active::before" pseudo-element does not animate
    And its opacity is fixed at 0.5
    And the contract is enforced by the existing globals.css media query

  @frontend
  Scenario: Banner is a link to the active problem's agentbook page
    Given the banner is showing problem "P-1"
    When the user activates the title with mouse or keyboard
    Then the browser navigates to "/memories/P-1"
    And the link uses the shared "focusRing" utility for keyboard focus

  @frontend
  Scenario: A11y — aria-live announces transitions politely
    Given a screen reader is attached
    And the banner has role "status"
    And the banner has aria-live "polite"
    And the banner has aria-atomic "false"
    When the active problem changes from "P-1" to "P-2"
    Then the screen reader announces the new title and confidence
    And announcements are debounced so two transitions within 1 second yield one announce
    And the idle copy is announced when the state transitions to idle

  @frontend
  Scenario: Banner reuses existing CSS tokens with no new ones introduced
    When the banner is rendered in either active or idle state
    Then the rendered DOM uses class "research-active" for the active container
    And the rendered DOM uses class "researching-dot" for the indicator
    And the rendered DOM uses the "Researching" badge variant
    And no new CSS custom properties are defined for this feature

  @frontend
  Scenario: Long problem descriptions are truncated client-side
    Given the snapshot payload's "description" is at the 300-character server cap
    When the banner renders that description
    Then the visible text uses Tailwind class "line-clamp-1"
    And the underlying anchor's accessible name is the full description

  # ============================================================
  # Server emitter behaviour
  # ============================================================

  @backend
  Scenario: Heartbeat keeps proxies from closing the SSE stream
    Given the SSE connection has been open for 25 seconds with no state change
    When the heartbeat timer fires
    Then the server writes a comment line beginning with ":heartbeat"
    And the line is terminated by a blank line
    And the client's onmessage handler is not invoked
    And the connection stays open past typical 30s proxy timeouts

  @backend
  Scenario: Server hard-closes idle streams after 15 minutes
    Given the SSE connection has been open for 15 minutes
    When the hard-timeout deadline elapses
    Then the server closes the response stream cleanly
    And the client EventSource reconnects transparently
    And the new connection emits a fresh "snapshot" event as its first frame

  @backend
  Scenario: Active backend caches last_cycle_at for 10 seconds in-process
    Given a single SSE connection is open
    And research_cycles is queried for "MAX(created_at)" on the first poll
    When subsequent polls run within 10 seconds
    Then the worker reuses the cached "last_cycle_at" value
    And no new query is issued for "MAX(research_cycles.created_at)"

  @backend
  Scenario: Event payload exposes only public fields
    When the server emits a "research_started" event
    Then the JSON payload contains keys "problem_id", "description",
      "solution_count", "best_confidence", "research_started_at", "now"
    And the payload contains no agent identifiers
    And the payload contains no API keys
    And the payload contains no email addresses
    And the payload contains no solution markdown bodies

  @backend
  Scenario: list_being_researched honours the 360s window
    Given problem "A" has research_started_at 359 seconds ago
    And problem "B" has research_started_at 361 seconds ago
    And problem "C" has research_started_at set to NULL
    When list_being_researched is called with timeout_seconds=360
    Then the result includes "A"
    And the result excludes "B"
    And the result excludes "C"

  @backend
  Scenario: Toggle-rate metric exposes the centralised-poller promotion threshold
    Given the SSE handler emits a structured log line on each "research_started"
      and "research_ended" event
    When operators query the log stream over a 60-second window
    Then the observed toggle rate (events per second) is computable from the logs
    And exceeding 10 toggles per second is the documented signal to promote
      to the centralised poller described in architecture.md §1
    And no production alert fires below that threshold

  @backend
  Scenario: get_latest_cycle_at returns None on empty research_cycles
    Given the research_cycles table is empty
    When get_latest_cycle_at is called
    Then the result is None
    And the snapshot's "last_cycle_at" field serialises as null
