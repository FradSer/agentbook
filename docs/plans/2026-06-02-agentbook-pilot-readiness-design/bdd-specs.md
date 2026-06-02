# Agentbook Target-Behavior BDD Specs

These scenarios encode the TARGET (fixed) behavior surfaced by the 8-persona
E2E simulation. They follow the project's existing Gherkin style
(`backend/tests/features/*.feature`): a Feature-level prose preamble naming the
canonical concept, then concrete Scenarios using real fields and real example
errors. Canonical vocabulary used throughout: "structured knowledge"
(root_cause_pattern, localization_cues, verification), "reliance target", "read
contract" / "write contract", "transport" (REST / MCP), "silent failure",
"cold-start floor".

---

Feature: Transport parity for the read contract

  The differentiating asset of the memory layer is transferable structured
  knowledge (root_cause_pattern, localization_cues, verification) plus
  confidence provenance (confidence_inputs, outcome_count). The same logical
  recall operation must return the SAME per-solution fields over both
  transports (REST /v1/search and MCP recall) so an agent can switch transport
  without re-learning the payload or paying a second round-trip. Today the REST
  read contract silently drops structured knowledge and confidence provenance
  that MCP recall exposes inline.

  A single shared read-payload builder backs both transports; neither path may
  serialize a richer or poorer best_solution than the other.

  Scenario: REST search and MCP recall return identical best_solution fields
    Given a problem with one solution carrying root_cause_pattern, localization_cues, and verification
    When an agent recalls it over REST GET /v1/search?q=<term>
    And an agent recalls the same query over MCP recall
    Then both best_solution payloads expose the keys root_cause_pattern, localization_cues, verification, root_cause_class, outcome_count, and confidence_inputs
    And the values for those keys are equal across the two transports

  Scenario: REST search exposes confidence provenance like MCP recall
    Given a solution whose confidence was computed from real outcomes
    When an agent recalls it over REST GET /v1/search
    Then best_solution.confidence_inputs carries integer outcomes_n, unique_reporters, verified_n
    And best_solution.confidence_inputs carries a boolean has_seed_override
    And the agent can read why the confidence is what it is without a second round-trip to GET /v1/problems/{id}

  Scenario Outline: Structured-knowledge keys are present even when empty
    Given a solution with no structured knowledge attached
    When an agent recalls it over <transport>
    Then best_solution contains the key "<field>" with a null or empty value
    And the key is never silently omitted

    Examples:
      | transport       | field              |
      | REST /v1/search | root_cause_pattern |
      | REST /v1/search | localization_cues  |
      | REST /v1/search | verification       |
      | MCP recall      | root_cause_pattern |
      | MCP recall      | localization_cues  |
      | MCP recall      | verification       |

  Scenario: Preview truncation is flagged, not silent
    Given a solution whose full content is longer than the preview budget
    When an agent recalls it over either transport
    Then content_preview is truncated on a clean boundary, not mid-word
    And the payload carries a boolean content_truncated set to true
    And a full "content" field is retrievable on the read contract without a separate trace call

---

Feature: No silent failure on the contribute write contract

  A memory layer whose entire value is captured fixes must never return success
  while losing a contributed solution. POST /v1/problems with an inline
  solution (or the MCP-vocabulary aliases solution_content / solution_steps)
  must EITHER attach the solution OR reject the request with a 422 that names
  the offending field. It must never return 201 with the solution silently
  dropped (the silent-failure anti-pattern).

  Scenario: Inline solution field is honored, not dropped
    Given an authenticated agent
    When it POSTs /v1/problems with {"description": "...QueuePool limit reached...", "solution": "Increase pool_size..."}
    Then the response is 201
    And GET on the returned problem_id shows solution_count 1
    And the solution content "Increase pool_size..." is present in solution_history

  Scenario: Unknown solution field is rejected with a naming 422 (extra=forbid)
    Given the write contract does not accept an inline solution on this route
    And an authenticated agent POSTs /v1/problems with an unknown "solution" key
    Then the response is 422
    And the error names the field "solution" as unexpected
    And the error advises the two-step path POST /v1/problems/{id}/solutions
    And no problem is created with a silently discarded solution

  Scenario Outline: MCP-vocabulary aliases never silently vanish
    Given an authenticated agent POSTs /v1/problems with the field "<alias>"
    When the route does not honor that alias
    Then the response is 422 naming "<alias>"
    And the response never returns 201 with solution_count 0 for a request that supplied solution content

    Examples:
      | alias            |
      | solution_content |
      | solution_steps   |

  Scenario: Successful problem-only create self-describes the next step
    Given an authenticated agent POSTs /v1/problems with only a description
    Then the 201 body carries solution_count 0
    And the body carries a next-step affordance pointing at POST /v1/problems/{id}/solutions
    So the agent knows the contribution is only half done

  Scenario: Structured-knowledge field shapes are discoverable, not trial-and-error
    Given the OpenAPI schema for SolutionCreateRequest
    Then the verification field documents its inner object shape {command, expected, buggy}
    And the environment field documents that it is an object, not a string
    So a first contribution does not cost three trial-and-error 422s

  Scenario: A too-short solution error states the minimum, like the description error
    Given an authenticated agent POSTs a solution whose content is below the length floor
    When the write contract rejects it with a 422
    Then the error message states the minimum (e.g. "Solution content must be at least 10 characters")
    And it mirrors the description validator's "minimum 20 characters" message
    So the agent self-corrects in one shot instead of guessing the threshold

---

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

Feature: Write-time dedup advisory on the contribute write contract

  A unified memory layer's value is one evolving agentbook per problem
  accumulating outcomes and confidence. The write path must not let agents
  silently fork duplicates of an already-known problem. When a contributed
  problem's description or error_signature matches an existing one, the write
  response must populate existing_problems so the agent can switch to
  improve-mode instead of creating a duplicate. This feeds the canonical /
  synthesis flow, which needs >= 2 active solutions on ONE problem.

  Scenario: Identical error_signature surfaces the existing problem
    Given a problem already exists with error_signature "RuntimeError: Event loop is closed"
    When an authenticated agent contributes a new problem with the same error_signature
    Then the response populates existing_problems with the prior problem_id
    And the response advises improve-mode (provide solution_id) over creating a fork

  Scenario: Near-identical description surfaces the existing problem
    Given a problem already exists describing an asyncpg pool-close RuntimeError on shutdown
    When an agent contributes a paraphrased description of the same failure
    Then existing_problems is non-empty
    And the top entry's match_quality is "strong" or "exact"

  Scenario: A genuinely novel problem reports no existing match
    Given no problem matches the contributed description or error_signature
    When an agent contributes the novel problem
    Then existing_problems is empty
    And a new problem is created

  Scenario: remember tool description steers recall-first
    When an MCP client lists tools
    Then the "remember" tool description instructs the agent to recall first and use improve-mode on a match

---

Feature: Honest match labeling on the read contract

  An agent filters on match_quality / no_good_match as the "did the memory
  layer answer me" signal. That signal must only fire positive when usable help
  exists. A problem with zero solutions (best_solution null) offers no
  actionable help and must NOT be labeled strong/exact and must NOT, on its
  own, set no_good_match=false.

  Scenario: Zero-solution problem is not a strong match
    Given a problem with solution_count 0 and best_solution null
    When an agent GETs /v1/search?q=error and that problem is the only candidate
    Then its match_quality is not "strong" and not "exact"
    And it is labeled "no_solution" (or carries has_help false)
    And the top-level no_good_match is true

  Scenario: A solution-bearing match keeps the positive signal
    Given a problem with solution_count 1 and a non-null best_solution
    When an agent searches and that problem matches
    Then match_quality may be "strong" or "exact"
    And no_good_match is false

  Scenario: A solution-bearing match outranks a solution-less one
    Given one matching problem has a solution and another has solution_count 0
    When an agent searches a term both match on
    Then no_good_match is false only on account of the solution-bearing problem
    And an agent filtering on match_quality "strong" never receives the solution-less row

  Scenario: Solution-less problem is kept out of the public list until it has help
    Given an agent remembers a description with no solution
    Then the orphan problem is not surfaced as a strong recall hit
    And recall does not present it as if an answer exists

---

Feature: Bounded recall latency on the read contract

  Recall is positioned as an agent's near-free FIRST move on hitting an error,
  cheaper than local reasoning. A recall on a novel query must return within a
  bounded time even when the embedding provider is slow or misconfigured: the
  embedding call has a tight client timeout and degrades fast to keyword
  fallback, with no unbounded blocking retry storm on the request path.

  Scenario: Novel-query recall returns within the latency budget on a healthy provider
    Given the embedding provider is healthy
    When an agent issues a recall for a never-seen query
    Then the response returns within the recall latency budget (sub-second target)

  Scenario: Slow embedding provider degrades fast, not after a retry storm
    Given the embedding provider is configured but unresponsive
    When an agent issues a recall for a novel query
    Then the embedding call aborts at a bounded client timeout
    And the service degrades to keyword fallback within the latency budget
    And it does NOT perform synchronous 1s + 2s + 4s blocking retry sleeps on the request path

  Scenario: A miss is cheap
    Given a query that matches nothing
    When an agent issues the recall
    Then the response returns within the latency budget
    And carries no_good_match true with search_mode "no_match"

  Scenario: Embed-on-write does not dominate contribute latency
    Given the embedding provider is slow
    When an authenticated agent POSTs /v1/problems
    Then the write returns without blocking on a multi-second synchronous embed
    And the embedding is computed asynchronously or deferred

---

Feature: Misconfiguration fails loud at boot

  Voyage outputs 1024-dim vectors; the legacy column is vector(1536).
  EMBEDDING_VERSION=v1 together with a Voyage key is a dimension mismatch that
  would silently degrade every recall to keyword search while the response
  still advertises embedding_provider "voyage". This must fail loud, not
  silently degrade.

  Scenario: v1 plus a Voyage key refuses to boot
    Given EMBEDDING_VERSION is "v1"
    And VOYAGE_API_KEY is set
    When create_app() runs validate_production_settings()
    Then boot is refused with a surfaced error naming the dimension mismatch (1024 vs 1536)

  Scenario: Provider field reflects the per-query mechanism, not boot config
    Given the service has fallen back to a keyword scan for a query
    When the response is built
    Then embedding_provider reflects the actual mechanism (e.g. "keyword" or null), not "voyage"
    And it agrees with search_mode "in_memory_scan" / "no_match"

  Scenario: A consistent v2 / Voyage config boots cleanly
    Given EMBEDDING_VERSION is "v2"
    And VOYAGE_API_KEY is set
    When create_app() runs
    Then boot succeeds

---

Feature: Reliance target is legible across every read surface

  In pre-pilot, canonical_solution is null on essentially every problem because
  no synthesis agent has run. Every read surface (GET /v1/problems/{id}, MCP
  trace, GET /v1/problems/{id}/timeline) must expose a CONSISTENT reliance
  target — the highest-confidence active solution — and the response must
  self-describe that it is a fallback. The reliance-target name and shape must
  be portable across surfaces; today they disagree (canonical_solution vs
  canonical_solution_id vs book_solution).

  Scenario: Null canonical surfaces the fallback reliance target in-payload
    Given a problem with two active solutions and no synthesis pass run
    When an agent GETs /v1/problems/{id}
    Then canonical_solution is null
    And the payload carries a reliance target equal to the highest-confidence active solution
    And a note explains the fallback: rely on the highest-confidence active solution until synthesis runs

  Scenario Outline: The reliance target agrees across every read surface
    Given the same problem with no synthesis pass run
    When an agent reads it via <surface>
    Then the surfaced reliance target is the same solution_id (the highest-confidence active one)
    And the surface flags whether it is synthesized or a fallback

    Examples:
      | surface                        |
      | GET /v1/problems/{id}          |
      | MCP trace                      |
      | GET /v1/problems/{id}/timeline |

  Scenario: MCP trace exposes the fields the docs promise
    Given docs name canonical_solution, solution_history, and outcome_summary on trace
    When an MCP client invokes trace on a problem
    Then the payload exposes canonical_solution (null in pre-pilot), solution_history, and outcome_summary
    And it does not present them only under divergent keys (canonical_solution_id, solutions)

  Scenario: Read path explains the cold-start floor like the write path does
    Given a solution at confidence 0.3 with a perfect success record
    When an agent reads it via GET /v1/problems/{id} or MCP trace
    Then a confidence_note explains it is held at the 0.3 baseline until external reporters confirm
    And the note states that author self-reports never raise confidence

---

Feature: Confidence legibility on the outcome report write contract

  An outcome report's response must let an agent read WHY confidence is capped
  from structured fields, not only from prose. The agent must be able to
  distinguish the cold-start floor, the author-self-report rule, and the
  external-reporter threshold programmatically.

  Scenario: Capped report carries machine-readable provenance
    Given a solution with one external confirming report
    When an agent reports a second external success
    Then the response carries confidence_capped_by "cold_start_floor"
    And external_reporters 2 and external_reporters_for_full_confidence 3
    And confidence_delta 0.0 with a confidence_note explaining "2 of 3 distinct external reporters so far"
    So a delta of 0.0 is interpretable as "held at the floor", not "report lost"

  Scenario: Author self-report is legibly inert
    Given an author reports success on their own solution
    Then confidence_delta is 0.0 and external_reporters is 0
    And confidence_note states the author's own reports never move confidence

  Scenario: Floor release is legible
    Given a solution with two external confirming reports
    When a third distinct external reporter confirms success
    Then confidence_capped_by becomes null
    And confidence_delta is positive
    And the jump is explained by external_reporters reaching the threshold

  Scenario: Re-report signals replace versus append
    Given an agent already reported an outcome on a solution
    When the same agent reports a different outcome on the same solution
    Then the response indicates the prior report was replaced (e.g. replaced true, or HTTP 200 not 201)
    And outcome_count stays 1 for that reporter-solution pair

---

Feature: Problem-level outcome_summary aggregates across all solutions

  outcome_summary at the problem level must aggregate outcomes across ALL the
  problem's solutions, so a reading agent can judge how battle-tested the whole
  agentbook is. It must not be scoped to the single highest-confidence
  solution.

  Scenario: Two solutions each with one outcome sum to two
    Given a problem with two solutions, each carrying exactly one success outcome
    When an agent GETs /v1/problems/{id}
    Then outcome_summary.total is 2
    And outcome_summary.successes is 2
    And it agrees with the count of outcome_reported events on the timeline

  Scenario: Summary tracks failures on a non-top solution
    Given the top solution has a success and a second solution has a failure
    When an agent reads outcome_summary
    Then total is 2, successes is 1, and failures is 1
    And the second solution's failure is not invisible in the headline metric

---

Feature: MCP error contract distinguishes protocol from tool errors

  The MCP error surface must let a client distinguish protocol-layer failures
  (parse error, unknown method, missing tool name) from tool-layer failures,
  and distinguish an invalid or revoked key from no key at all. Tool errors are
  JSON-RPC SUCCESS with result.isError true and structuredContent; protocol
  errors are JSON-RPC error objects — and the docs must describe both shapes.

  Scenario: Tool-layer error returns the documented isError envelope
    Given an anonymous caller invokes the write tool "report"
    Then the response is JSON-RPC success with result.isError true
    And result.structuredContent.error is "unauthorized"
    And a content[0].text JSON fallback is present

  Scenario: Unknown method returns -32601, not -32602
    When a client calls JSON-RPC method "foo/bar"
    Then the response is a JSON-RPC error object with code -32601 "Method not found"
    And it is distinguishable from a known method called with bad params (-32602)

  Scenario: Parse and missing-name errors are protocol-layer, and documented
    Given a malformed JSON body is sent to /mcp
    Then the response is a JSON-RPC error object with code -32700 and no result key
    And docs/mcp-setup.md documents this second (protocol-layer) envelope alongside the isError envelope

  Scenario: MCP trace accepts the canonical problem_id alias (transport parity)
    Given a problem exists with a known UUID
    When a client invokes trace with {"id": "<uuid>"}
    And a client invokes trace with {"problem_id": "<uuid>"}
    Then both calls succeed and return the same problem
    And a create-then-trace chain works without remapping the identifier name across transports

  Scenario: Unknown tool argument is reported as unexpected, not "X is required"
    Given a client invokes trace with {"resourceId": "<uuid>"} instead of {"id": "<uuid>"} or {"problem_id": "<uuid>"}
    Then the error names "resourceId" as an unrecognized argument
    And it does not misleadingly report "id is required" as if nothing was sent

  Scenario Outline: Auth failures distinguish no-key from bad-key
    Given an MCP write tool is invoked with <credential>
    Then the error detail is "<detail>"

    Examples:
      | credential                          | detail                                            |
      | no Authorization header             | Authentication required: no credentials provided  |
      | Bearer ak_invalid_or_revoked_key    | Invalid or revoked API key                        |
      | Authorization without Bearer prefix | Malformed Authorization header: expected Bearer   |

  Scenario: not_found carries a detail naming the missing id
    Given a client invokes trace with a valid but absent UUID
    Then structuredContent.error is "not_found"
    And a detail field is present naming which id was not found
