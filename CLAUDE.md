# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **Delphix DCT API MCP Server** (`dct-mcp-server`) — a Model Context Protocol (MCP) server that gives AI assistants structured access to the Delphix Data Control Tower (DCT) API for test data management. Requires **Python 3.11+**.

## Running the Server

**Recommended (uvx — no clone needed):**
```bash
uvx --from git+https://github.com/delphix/dxi-mcp-server.git dct-mcp-server
```

**Install via pip:**
```bash
pip install git+https://github.com/delphix/dxi-mcp-server.git
dct-mcp-server  # CLI entry point
```

**From a local clone (development):**
```bash
export DCT_API_KEY=<your-api-key>
export DCT_BASE_URL=<your-dct-url>   # No /dct suffix

./start_mcp_server_uv.sh      # Recommended (uv)
./start_mcp_server_python.sh  # Alternative (venv)
```

When running standalone (dev mode), the server prints the port it listens on (e.g. `http://127.0.0.1:6790`). MCP clients can then connect using just the port — no env vars needed in the client config:
```json
{ "mcpServers": { "delphix-dct": { "port": 6790 } } }
```

Key optional env vars:
- `DCT_TOOLSET` — `self_service` (default), `auto`, `continuous_data_admin`, `platform_admin`, `reporting_insights`, `self_service_provision`
- `DCT_VERIFY_SSL` — default `false`
- `DCT_LOG_LEVEL` — default `INFO`
- `DCT_TIMEOUT` — seconds, default `30`
- `DCT_MAX_RETRIES` — default `3`
- `IS_LOCAL_TELEMETRY_ENABLED` — default `false`
- `DCT_LOG_DIR` — optional override for log directory; useful in Docker to write logs to a mounted volume path

No automated test suite exists. Testing is done by connecting an MCP client to the running server. Logs are written to `logs/dct_mcp_server.log` (rotating) and `logs/sessions/{session_id}.log` (telemetry).

## Architecture

### Persona-Based Toolsets

The server exposes different sets of tools depending on `DCT_TOOLSET`. Each toolset is defined in a text file under `src/dct_mcp_server/config/toolsets/` with the format:

```
# TOOL N: tool_name - Description
METHOD|/endpoint/path|action_name
```

Toolsets can inherit from others using `@inherit:parent_name`. No code changes are needed to add endpoints to a toolset — only the `.txt` file needs editing.

### Grouped Tools Pattern

Instead of one MCP tool per API endpoint, related endpoints are grouped under a single tool with an `action` parameter (e.g., `vdb_tool(action="search", ...)`, `vdb_tool(action="delete", ...)`). This reduces tool count for the AI context. Each action maps to one DCT API endpoint.

### Auto Mode

When `DCT_TOOLSET=auto`, the server starts with only 5 meta-tools. The AI can dynamically enable/disable toolsets at runtime (using `tools/list_changed` MCP notifications) without restarting the server.

Client compatibility for dynamic tool switching:
- Claude Desktop, Cursor, Continue.dev — fully supported
- VS Code Copilot — requires chat restart after `enable_toolset`; use a fixed toolset for best experience

### Confirmation System

Destructive operations require a two-step call pattern. The first call returns a `confirmation_required` status; re-calling with `confirmed=True` executes the operation:

```python
vdb_tool(action="delete_vdb", vdbId="vdb-123")
# → {"status": "confirmation_required", "confirmation_level": "manual", ...}

vdb_tool(action="delete_vdb", vdbId="vdb-123", confirmed=True)
# → {"status": "success", ...}
```

Confirmation rules are defined in `src/dct_mcp_server/config/mappings/manual_confirmation.txt`. Format:

```
METHOD|path_pattern|confirmation_level|message_template
```

Confirmation levels: `standard`, `elevated`, `manual`, `retention_check:N`, `policy_impact_check:N`.

### Dynamic Tool Generation

Tools can be generated at runtime from an OpenAPI spec via `src/dct_mcp_server/tools/core/tool_factory.py` and `src/dct_mcp_server/toolsgenerator/driver.py`. The server checks `$TEMP/dct_mcp_tools/` first, then falls back to the bundled spec. Pre-built tools in `tools/*_endpoints_tool.py` serve as a fallback if generation fails.

### Key Source Layout

```
src/dct_mcp_server/
├── main.py                    # Entry point; lifespan, FastMCP setup
├── config/
│   ├── config.py              # Env var loading/validation
│   ├── loader.py              # Toolset + confirmation rule loading
│   ├── toolsets/*.txt         # Persona toolset definitions
│   └── mappings/manual_confirmation.txt
├── core/
│   ├── logging.py             # Global + session logging setup
│   ├── session.py             # Session management, telemetry
│   ├── decorators.py          # @log_tool_execution decorator
│   └── exceptions.py
├── dct_client/client.py       # Async HTTP client with retry/backoff
├── tools/
│   ├── __init__.py            # Dynamic tool registration
│   ├── *_endpoints_tool.py    # Pre-built grouped tools
│   └── core/
│       ├── meta_tools.py      # Auto-mode meta-tools
│       └── tool_factory.py    # Dynamic tool generation
└── toolsgenerator/driver.py   # OpenAPI spec processor
```

### Startup Flow

`main.py` → initialize `DCTAPIClient` → `register_all_tools()` (dynamic module discovery in `tools/__init__.py`) → FastMCP stdio transport. Shutdown: lifespan context manager closes HTTP client and ends telemetry session.
