# Testing Rules

Based on the jira information or description of the change, determine which toolsets and scenarios to test against. Use the appropriate prompt files from `.claude/test/testing/` to guide your testing.

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

Generate a final test report summarizing the above and any issues encountered, and attach it to the PR for reviewer reference.

## Automated Testing via pytest

Use `pytest` + `pytest-asyncio` + `fastmcp` client to spawn the local MCP server as a subprocess
and drive it over stdio transport. This is the automated testing approach for this project.

Test files live in `tests/` and follow the naming pattern `tests/<ticket>-test.py`.

**Setup**:
```bash
# Install dependencies (see .claude/test/test-infra.md for full setup)
uv sync   # or: pip install -r requirements.txt && pip install -e .

# Install test dependencies
pip install pytest pytest-asyncio
# fastmcp is already in requirements.txt
```

**How a test file is structured**:
- A module-scoped `pytest_asyncio` fixture that reads `DCT_API_KEY` and `DCT_BASE_URL` from
  `.claude/settings.local.json` (under `mcpServers.dct.env`) and opens an async `fastmcp.Client`
  using `StdioServerParameters(command="bash", args=[<launch_script>], env={...})`. Pick the
  launch script the same way `test-infra.md` does: `start_mcp_server_uv.sh` if `uv` is on PATH,
  otherwise `start_mcp_server_python.sh`
- One `async def test_*` function per scenario, calling `client.call_tool(name, arguments)` and
  asserting the response (expected keys present, no error fields)
- See `.claude/test/test-infra.md` for the full launch script and env var names

**Run tests**:
```bash
# Precheck: credentials must be in .claude/settings.local.json (see test-infra.md)
python3 -c "import json; e=json.load(open('.claude/settings.local.json'))['mcpServers']['dct']['env']; assert e.get('DCT_API_KEY') and e.get('DCT_BASE_URL'), 'missing creds'"

pytest tests/ -v
```

## Toolset Test Prompt Files

Full prompt lists for each toolset are in `.claude/test/testing/`:

| File | Toolset | Prompts |
|------|---------|---------|
| [testing/auto.md](testing/auto.md) | `auto` | 57 |
| [testing/self_service.md](testing/self_service.md) | `self_service` | 70 |
| [testing/self_service_provision.md](testing/self_service_provision.md) | `self_service_provision` | 70 inherited + 69 new |
| [testing/continuous_data_admin.md](testing/continuous_data_admin.md) | `continuous_data_admin` | 431 |
| [testing/platform_admin.md](testing/platform_admin.md) | `platform_admin` | 198 |
| [testing/reporting_insights.md](testing/reporting_insights.md) | `reporting_insights` | 79 |
