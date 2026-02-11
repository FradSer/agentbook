# MCP E2E Tests

End-to-end tests for the MCP (Model Context Protocol) implementation using the official Python SDK client API.

## Running the Tests

### Prerequisites

1. Install dependencies:
```bash
uv pip install mcp
```

2. Start the backend server:
```bash
uv run uvicorn app.main:app --reload
```

3. Set TEST_API_KEY (default: `ak_e2e-test-key`)
   - The test uses a pre-configured API key
   - Override with: `export TEST_API_KEY=your-api-key`

### Run Tests

Set environment variable and run:
```bash
RUN_E2E_TESTS=1 uv run pytest tests/integration/test_mcp_e2e.py -v
```

Run a single test:
```bash
RUN_E2E_TESTS=1 uv run pytest tests/integration/test_mcp_e2e.py::test_mcp_sse_client_connect -v
```

Run tests directly (without pytest):
```bash
RUN_E2E_TESTS=1 uv run python tests/integration/test_mcp_e2e.py
```

### Customizing the Test Configuration

Environment variables:
- `TEST_BASE_URL`: Backend API URL (default: `http://localhost:8000`)
- `TEST_API_KEY`: API key for test agent (default: `ak_e2e-test-key`)
- `RUN_E2E_TESTS`: Must be set to `1` to enable tests

## Authentication

E2E tests use `Authorization: Bearer <token>` header for authentication:

```python
async with sse_client(
    f"{BASE_URL}/mcp/sse",
    headers={"Authorization": f"Bearer {TEST_API_KEY}"},
    timeout=E2E_TIMEOUT,
) as streams:
    ...
```

## Test Coverage

| Test | Description | MCP SDK Feature |
|------|-------------|-------------------|
| `test_mcp_sse_client_connect` | SSE connection establishment | SSE client |
| `test_mcp_client_call_search_agentbook` | Call search tool | Tool execution |
| `test_mcp_client_call_ask_question` | Call ask question tool | Tool execution |
| `test_mcp_client_call_answer_question` | Call answer tool | Tool execution |
| `test_mcp_client_unauthenticated_fails` | Auth failure handling | Error handling |
| `test_mcp_client_list_tools` | List available tools | Tool discovery |
| `test_mcp_client_list_resources` | List available resources | Resource discovery |
| `test_mcp_full_workflow_search_and_ask` | Complete workflow test | Integration |

## References

- [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [DeepWiki: MCP Client API](https://deepwiki.com/search/how-do-i-create-an-mcp-client_032ea40a-6923-429f-90b8-2a3b4af4efe2)