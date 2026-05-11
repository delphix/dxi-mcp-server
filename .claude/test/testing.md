# Testing Rules

Based on the jira information or description of the change, determine which toolsets and scenarios to test against. Use the appropriate prompt files from `.claude/test/testing/` to guide your testing.

## Testing Is Driven by Claude

Testing for this repository is performed by **Claude** running in this checkout — not by a human typing into a separate MCP client. The dct MCP server is configured in `.mcp.json`, so Claude calls its tools directly to exercise scenarios against a live DCT instance and verifies the responses.

Two complementary tracks, both driven by Claude:

1. **Scenario execution** — Claude executes the prompt lists in `.claude/test/testing/<toolset>.md` against a live DCT and reports outcomes per prompt.
2. **Automated regression (`pytest`)** — Claude authors and runs `tests/<ticket>-test.py` files that spawn the server as a subprocess and assert tool responses programmatically. Use for changes whose behaviour is deterministic enough to re-run in CI.

## What to Verify for Each Change

| Change type | What to verify |
|-------------|---------------|
| New toolset entry (`.txt`) | Tool registers, action executes against DCT, response is correct |
| New confirmation rule | First call returns `confirmation_required`; re-call with `confirmed=True` executes |
| New pre-built tool module | `register_tools()` runs at startup; tool is exposed via the MCP server |
| `TOOL_TO_MODULE` mapping change | Correct module loads for the affected toolset |
| Dynamic tool generation change | Generated module in `$TEMP/dct_mcp_tools/` takes priority over pre-built |
| Auto mode change | `enable_toolset` / `disable_toolset` works; subsequent tool listing reflects the change |

## DCT Toolset Coverage

When changing toolset configs or tool implementations, exercise at minimum:
- The specific toolset(s) the change affects
- `auto` mode if the change touches dynamic enable/disable behaviour

## Track 1 — Scenario Execution

Steps Claude follows for a change:

1. Confirm credentials are present — `.claude/settings.local.json` under `mcpServers.dct.env` must have `DCT_API_KEY` and `DCT_BASE_URL` (see `.claude/test/test-infra.md`).
2. Set `DCT_TOOLSET=<toolset>` for the change in `.mcp.json` and restart the dct MCP server so the new toolset is registered.
3. Open the matching scenario file `.claude/test/testing/<toolset>.md` and execute each prompt by calling the relevant dct MCP tool. Prompts are chained — IDs/values discovered in earlier prompts are reused in later ones.
4. For confirmation-flow prompts: the first call should return `status=confirmation_required`. Re-issue the same call with `confirmed=True` and verify success.
5. Record results into the PR test report (see "Test Report" below).

## Track 2 — Automated `pytest` Regression

Use `pytest` + `pytest-asyncio` + `fastmcp` client to spawn the local MCP server as a subprocess and drive it over stdio transport.

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

## Test Report (PR Evidence)

PR descriptions must include a Claude-generated test report containing:

- Toolset(s) tested and the `DCT_TOOLSET` value used
- DCT version exercised against
- Scenario prompts executed (from `.claude/test/testing/<toolset>.md`) with pass / fail / skipped + reason per prompt
- Any `pytest` runs invoked and their output
- Issues encountered and follow-ups

Attach the report to the PR for reviewer reference.

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
