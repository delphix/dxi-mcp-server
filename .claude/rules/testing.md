# Testing Rules

## No Automated Test Suite

There is no unit or integration test suite in this repository. Do not create mock-based unit tests — the FastMCP framework and DCT API interactions are too tightly coupled to a live server for mocks to be reliable.

## Testing Is Done via Claude Using the dct MCP Server

Claude can test the server directly by starting it via the test infrastructure (`.claude/test-infra.md`) and calling `mcp__dct__*` tools in the current session. Credentials are read from `.claude/settings.local.json` at runtime — never hardcode them.

The `test-infra-creation` step in `feature-implement` handles server startup automatically before tests run.

### How to Run a Test Scenario

Once the server is running, invoke the relevant `mcp__dct__*` tool directly:

1. Call a read operation (e.g. list VDB groups or bookmarks) — verify the response matches expected DCT output
2. Call a write operation with `confirmed=False` — verify it returns `confirmation_required: true`
3. Re-call with `confirmed=True` — verify it executes and returns a success response

If a tool is not visible in the session, the toolset is not enabled — check `DCT_TOOLSET` in `.claude/settings.local.json`.

Manual testing via real MCP clients (Claude Desktop, Cursor, VS Code Copilot) is still valid for verifying client-facing UX.

## Docker vs uv — Choosing the Right Test Path

The server must be tested using the same runtime path as the change being made:

| Change involves | Test using |
|-----------------|-----------|
| `Dockerfile`, container startup, image build | **Docker** (Path A in `.claude/test-infra.md`) |
| Tool configs (`.txt`), Python source, toolset logic | **uv** (Path B in `.claude/test-infra.md`) |
| Both (e.g. new tool + Dockerfile update) | **Docker** — it covers both paths |

When documenting test evidence, always record which startup path was used (Docker or uv).

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
