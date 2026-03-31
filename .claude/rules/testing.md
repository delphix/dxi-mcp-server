# Testing Rules

## No Automated Test Suite

There is no unit or integration test suite in this repository. Do not create mock-based unit tests — the FastMCP framework and DCT API interactions are too tightly coupled to a live server for mocks to be reliable.

## Testing Is Done via MCP Clients

Test by running the server locally and connecting a real MCP client (Claude Desktop, Cursor, VS Code Copilot) against a live DCT instance.

## What to Verify for Each Change

| Change type | What to verify |
|-------------|---------------|
| New toolset entry (`.txt`) | Tool appears in client, action executes against DCT, response is correct |
| New confirmation rule | First call returns `confirmation_required`; re-call with `confirmed=True` executes |
| New pre-built tool module | `register_tools()` is called at startup; tool appears in MCP client |
| `TOOL_TO_MODULE` mapping change | Correct module loads for the affected toolset |
| Dynamic tool generation change | Generated module in `$TEMP/dct_mcp_tools/` takes priority over pre-built |
| Auto mode change | `enable_toolset` / `disable_toolset` works; client reflects updated tool list |

## DCT Toolset Coverage

When changing toolset configs or tool implementations, test with at least:
- The specific toolset being modified
- A client that supports dynamic tool switching (Claude Desktop or Cursor) if changing auto mode
- VS Code Copilot if the change affects fixed-toolset behaviour

## Documenting Test Evidence in PRs

PR descriptions must include:
- Which MCP client was used
- Which toolset(s) were tested
- Which DCT version was used
- Specific actions/scenarios exercised
