# Task 008: Performance Test

**Type**: test
**Depends-on**: task-007-error-handling-impl

## Objective

Write performance tests for Streamable HTTP transport latency.

## BDD Scenario

```gherkin
Scenario: Connection establishment latency meets P99 target
  Given client sends 100 consecutive POST requests to establish sessions
  When measuring response times
  Then P99 latency is less than 100ms
  And no request exceeds 200ms
  And average latency is less than 50ms
```

## Files to Create

- `tests/performance/test_mcp_latency.py`

## Test Cases

1. **test_connection_establishment_p99_latency**
   - Send 100 initialize requests
   - Measure response times
   - Assert P99 < 100ms
   - Assert max < 200ms
   - Assert mean < 50ms

2. **test_stateless_mode_throughput**
   - Send 1000 requests with stateless=True
   - Measure requests per second
   - Assert throughput > 100 req/s

3. **test_concurrent_sessions**
   - Create 50 concurrent sessions
   - Assert all succeed within 5 seconds
   - Measure latency distribution

## Test Fixtures Required

- Performance test client with timing
- Statistical helpers for P99 calculation

## Verification

```bash
uv run pytest tests/performance/test_mcp_latency.py -v
# Expected: tests pass with latency metrics
```

## Commit

```
test(mcp): add performance tests for streamable http latency

Measure P99 latency, throughput, and concurrent session handling.
```