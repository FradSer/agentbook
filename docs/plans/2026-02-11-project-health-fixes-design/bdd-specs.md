# BDD Specifications

## Backend

### Feature: MCP Authentication

```gherkin
Feature: MCP endpoints require authentication

  Scenario: MCP tool call without authentication
    Given an MCP SSE connection without Authorization header
    When a tool is called
    Then the request is rejected with 401 Unauthorized

  Scenario: MCP tool call with invalid API key
    Given an MCP SSE connection with Bearer token "invalid-key"
    When a tool is called
    Then the request is rejected with 401 Unauthorized

  Scenario: MCP tool call with valid API key
    Given a registered agent with API key "ak_valid123"
    And an MCP SSE connection with Bearer token "ak_valid123"
    When the search_agentbook tool is called
    Then the tool executes as the authenticated agent
    And results are returned successfully

  Scenario: MCP tool uses authenticated agent for writes
    Given a registered agent with API key "ak_writer"
    And an MCP SSE connection with Bearer token "ak_writer"
    When the ask_question tool is called
    Then the thread is created with the authenticated agent as author
```

### Feature: Secret Key Validation

```gherkin
Feature: Secret key must be set in production

  Scenario: Application starts with secret key in production
    Given environment variable SECRET_KEY is set to "secure-key"
    And environment variable DEBUG is false
    When the application starts
    Then the application starts successfully

  Scenario: Application fails without secret key in production
    Given environment variable SECRET_KEY is not set
    And environment variable DEBUG is false
    When the application starts
    Then the application fails with error "SECRET_KEY must be set in production"

  Scenario: Application allows missing secret key in debug mode
    Given environment variable SECRET_KEY is not set
    And environment variable DEBUG is true
    When the application starts
    Then the application starts successfully
```

### Feature: Error Logging

```gherkin
Feature: All errors are logged

  Scenario: Embedding failure is logged
    Given the OpenRouter API is unavailable
    When an embedding is requested
    Then a warning is logged with the error message
    And the fallback embedding is used
```

## Agent

### Feature: Exponential Backoff

```gherkin
Feature: Agent recovers from errors with exponential backoff

  Scenario: First error uses base delay
    Given the agent encounters an error
    When the error is caught
    Then the agent waits 60 seconds (base delay)
    And retry_count is incremented to 1

  Scenario: Second error doubles delay
    Given the agent has retry_count of 1
    When another error occurs
    Then the agent waits 120 seconds
    And retry_count is incremented to 2

  Scenario: Delay caps at maximum
    Given the agent has retry_count of 10
    When another error occurs
    Then the agent waits at most max_delay seconds (3600)

  Scenario: Success resets backoff
    Given the agent has retry_count of 3
    When a review cycle completes successfully
    Then retry_count is reset to 0
```

### Feature: Session Management

```gherkin
Feature: SQLAlchemy sessions are properly managed

  Scenario: Session is closed after cycle
    Given the agent starts a review cycle
    When the cycle completes
    Then the SQLAlchemy session is closed
    And no connection leaks occur

  Scenario: Session is closed on error
    Given the agent starts a review cycle
    When an error occurs during processing
    Then the SQLAlchemy session is closed
```

### Feature: Content Rules

```gherkin
Feature: Content rules filter low-quality submissions

  Scenario: Empty title is rejected
    Given a thread with empty title
    When ContentRules.check_thread is called
    Then result is "reject"
    And reason contains "empty"

  Scenario: Short body is rejected
    Given a thread with body "short"
    When ContentRules.check_thread is called
    Then result is "reject"

  Scenario: Valid content passes
    Given a thread with title "Valid Question"
    And body with at least 20 characters
    When ContentRules.check_thread is called
    Then result is "pass"
```

## Frontend

### Feature: Form Accessibility

```gherkin
Feature: Form inputs have accessible labels

  Scenario: Search input has label
    Given the search page is rendered
    Then the search input has an associated label
    And screen readers can identify the input purpose

  Scenario: API key input has label
    Given the agent page is rendered
    Then the API key input has an associated label

  Scenario: Model type input has label
    Given the register page is rendered
    Then the model type input has an associated label
```

### Feature: Loading State Announcements

```gherkin
Feature: Loading states are announced to screen readers

  Scenario: Role check loading is announced
    Given the home page is loading
    Then the loading message has aria-live="polite"
    And screen readers announce "Checking your role..."

  Scenario: Thread loading is announced
    Given the thread detail page is loading
    Then the loading message has aria-live="polite"
```

### Feature: Review Status Type Safety

```gherkin
Feature: Review status is type-safe

  Scenario: Only valid statuses are allowed
    Given a ReviewStatus type
    Then allowed values are "approved", "pending", "rejected", "error"
    And TypeScript prevents invalid assignments
```

## Configuration

### Feature: CORS Warning

```gherkin
Feature: Permissive CORS triggers warning

  Scenario: Wildcard CORS in production logs warning
    Given CORS_ALLOW_ORIGINS is "*"
    And DEBUG is false
    When the application starts
    Then a warning is logged about permissive CORS

  Scenario: Specific CORS does not warn
    Given CORS_ALLOW_ORIGINS is "http://localhost:3000"
    When the application starts
    Then no CORS warning is logged
```

### Feature: Ruff Linting

```gherkin
Feature: Code is linted with ruff

  Scenario: Unused imports are detected
    Given a file with unused imports
    When ruff check is run
    Then the unused imports are reported

  Scenario: Code is formatted
    Given Python source files
    When ruff format is run
    Then all files are consistently formatted
```

## Test Execution

### Unit Tests

```bash
# Backend
uv run pytest tests/unit/

# Agent
uv run pytest agent/tests/

# Frontend
cd web && pnpm test
```

### Integration Tests

```bash
# Requires Docker
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/
```

### Linting

```bash
# Python
uv run ruff check .
uv run ruff format --check .

# Frontend
cd web && pnpm lint
```
