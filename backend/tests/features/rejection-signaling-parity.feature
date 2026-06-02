Feature: Transport parity for rejection signaling on the improve write contract

  A gated/rejected improvement must signal failure identically across
  transports, so a client keying off HTTP status or result.isError reaches the
  same conclusion on REST and MCP. Today the frozen gate's rejection arrives as
  REST 409 + error envelope but MCP 200 + isError:false (the rejection buried
  in the payload), so an MCP client believes a gated improvement succeeded.
  The gate decision (FROZEN math, confidence.py:149) is never altered — only
  the way its rejection is signalled is unified across transports.

  Scenario: A frozen-gate rejection is signalled identically on REST and MCP
    Given an improve submission the frozen gate rejects as "content_bloat"
    When an agent submits it over REST POST /v1/solutions/{id}/improve
    And an agent submits the same improvement over MCP remember improve-mode
    Then both transports signal rejection through the single authoritative field (non-2xx / result.isError true)
    And both carry the same reason "content_bloat" and the same next_action
    And a client keying off HTTP status or isError detects the rejection identically on both transports

  Scenario: An accepted improvement is signalled identically on REST and MCP
    Given an improve submission that lands in the cold-start acceptance window
    When an agent submits it over REST and over MCP
    Then both transports signal acceptance (2xx / result.isError false) with candidate_status "candidate"
    And neither transport reports success for a submission the other reports as rejected

---
