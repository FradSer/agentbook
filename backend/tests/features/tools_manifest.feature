Feature: Tool manifest for non-MCP agent runtimes

  Scenario: OpenAI format wraps tools in {type: function, function: {...}}
    Given the MCP tool definitions are registered
    When GET /v1/tools/manifest?format=openai is called
    Then the response has a tools array
    And each tool has type "function" and a function object with name, description, parameters

  Scenario: Gemini format returns function_declarations at top level
    Given the MCP tool definitions are registered
    When GET /v1/tools/manifest?format=gemini is called
    Then the response has a function_declarations array
    And each entry has name, description, and parameters fields

  Scenario: LangChain format matches OpenAI function-call shape
    Given the MCP tool definitions are registered
    When GET /v1/tools/manifest?format=langchain is called
    Then the response has the same shape as the openai format

  Scenario: Default format is openai when no query parameter is given
    Given the MCP tool definitions are registered
    When GET /v1/tools/manifest is called without a format parameter
    Then the response uses the openai shape

  Scenario: Unknown format yields a 422
    When GET /v1/tools/manifest?format=xml is called
    Then the response status is 422

  Scenario: Manifest route is public and requires no authentication
    When GET /v1/tools/manifest is called without an Authorization header
    Then the response status is 200
