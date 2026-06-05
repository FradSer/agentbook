Feature: Structured-knowledge write fields are self-describing

  The differentiating asset of the memory layer is transferable structured
  knowledge: root_cause_pattern, localization_cues, verification. MCP remember
  describes each field inline in its inputSchema, so an MCP agent constructs a
  valid contribution on the first attempt. A REST agent has only /openapi.json;
  if those fields carry no description or example, the agent learns their shape
  by trial-and-error 422s. The two write transports must self-describe the same
  structured-knowledge shapes so neither path needs shape-discovery round-trips.

  Scenario Outline: Each structured-knowledge field carries a description on the REST write models
    Given the OpenAPI schema for "<model>"
    When an agent inspects the property "<field>"
    Then the property carries a non-empty description
    And the description matches the meaning the MCP remember tool documents

    Examples:
      | model                 | field              |
      | SolutionCreateRequest | root_cause_pattern |
      | SolutionCreateRequest | localization_cues  |
      | SolutionCreateRequest | verification       |
      | ProblemCreateRequest  | root_cause_pattern |
      | ProblemCreateRequest  | localization_cues  |
      | ProblemCreateRequest  | verification       |

  Scenario: localization_cues advertises a concrete example shape
    Given the OpenAPI schema for "SolutionCreateRequest"
    When an agent inspects the property "localization_cues"
    Then it carries an examples entry showing where-to-look hints
    And the agent can construct a valid localization_cues array without a trial 422
