# Task 2.2: RED - Write Unit Test for Search Result Formatting

**BDD Reference**: Feature "search_agentbook MCP Tool" - Scenario "Search returns formatted Markdown results"

## Verification Command

```bash
uv run pytest tests/unit/test_mcp_formatters.py::test_format_search_results -v
```

**Expected Result**: Test fails with "ModuleNotFoundError" (formatting function not implemented yet)

## Implementation Details

Create unit tests in `tests/unit/test_mcp_formatters.py` for the search results formatting function.

### Test Requirements

Create tests that verify the `_format_search_results()` function handles:

1. **Normal case with results**
   - Input: List of search results with thread_id, title, tags, similarity_score, and top_solution
   - Expected output: Markdown with "# Search Results" header, result details, and top solution

2. **Empty results**
   - Input: Empty list
   - Expected output: "No matching questions found."

3. **Results without top solution**
   - Input: Results with no top_solution field or None value
   - Expected output: Results displayed without "Top Solution" section

4. **Multiple results**
   - Input: Multiple search results
   - Expected output: All results displayed in order with proper formatting

### Formatting Requirements

The formatted output should include:
- "# Search Results" header
- For each result:
  - "## {title}" subheader
  - "- ID: {thread_id}"
  - "- Tags: {comma-separated tags}"
  - "- Similarity: {score:.2f}"
  - "**Top Solution** (wilson: {score:.2f}):" if solution exists
  - Solution content preview if available
- "---" separator and "Found {count} matching question(s)." at the end

### BDD Scenario Mapping

- **Given**: Search returns results with similarity scores
- **When**: Formatter processes search results
- **Then**: Output contains Markdown with "# Search Results"
- **Then**: Similarity scores displayed with 2 decimal places
- **Then**: Results ordered by similarity descending

## Success Criteria

- Unit test file created or updated
- Test fails as expected (function not yet implemented)
- Test covers: normal case, empty results, no solution, multiple results
- Test verifies Markdown formatting correctness