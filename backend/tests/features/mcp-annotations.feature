Feature: MCP tool annotations

  Scenario: Registered tools advertise safety and world-interaction hints
    Given the MCP tool definitions are registered
    When an agent lists the available tools
    Then read-only tools declare readOnlyHint true
    And mutating tools declare readOnlyHint false
    And additive tools declare destructiveHint false
    And tools that call external providers declare openWorldHint true
