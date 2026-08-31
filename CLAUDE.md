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
- `DCT_TOOLSET` — `dynamic` (default), `self_service`, `continuous_data_admin`, `platform_admin`, `reporting_insights`, `self_service_provision`
- `DCT_VERIFY_SSL` — default `false`
- `DCT_LOG_LEVEL` — default `INFO`
- `DCT_TIMEOUT` — seconds, default `30`
- `DCT_MAX_RETRIES` — default `3`
- `IS_LOCAL_TELEMETRY_ENABLED` — default `false`
- `DCT_CONFIRMATION_TOKEN_TTL` — seconds, default `3600`; TTL for single-use confirmation tokens
- `DCT_CONFIRMATION_ENFORCEMENT` — `advisory` (default) or `strict`; in strict mode, non-elicitation clients are refused
- `DCT_CONFIRMATION_FALLBACK` — `keyword` (default) or `off`; keyword resolver catches ungated mutating operations
- `DCT_GRANT_TTL` — seconds, default `900`; TTL for scoped batch grants
- `DCT_BATCH_COUNTER_PERSISTENCE` — `off` (default) or `file`; opt-in persistence for velocity counters

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

Confirmation levels: `standard`, `elevated`, `manual`, `retention_check:N`, `policy_impact_check:N`, `batch_check:N:T` (velocity: trigger after N calls within T seconds).

The confirmation system was hardened in DLPXECO-14458 to add:
- **Single-use body-bound tokens** — HMAC includes `canonical_json(body)`; tokens are consumed on use and cannot be replayed
- **Differentiated levels** — `elevated` requires confirmed resource name; `manual` adds impact acknowledgement
- **Floor operations** — any HTTP DELETE or POST to `*/delete` cannot be bypassed by a grant; rules in `config/mappings/floor_operations.txt`
- **Batch grants** — `GrantStore` allows one user approval to cover an enumerated set of N calls
- **MCP elicitation** — `Context.elicit()` used when client declares elicitation capability; `DCT_CONFIRMATION_ENFORCEMENT=strict` refuses non-elicitation clients
- **Per-identity velocity detection** — `batch_check:N:T` rules keyed on `(caller_identity, method, path_template)`
- **Immutable audit events** — emitted for every gate decision regardless of telemetry opt-in (see `tools/core/audit.py`)

Read-shaped POSTs (e.g. `/vdbs/provision_by_snapshot/defaults`, `/snapshots/search`) are excluded from the keyword fallback via `config/mappings/read_exclusions.txt`.

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
│   └── mappings/
│       ├── manual_confirmation.txt   # Per-operation confirmation rules
│       ├── floor_operations.txt      # Non-bypassable floor operations
│       └── read_exclusions.txt       # POSTs excluded from keyword fallback
├── core/
│   ├── logging.py             # Global + session logging setup
│   ├── session.py             # Session management, telemetry; PROCESS_IDENTITY
│   ├── decorators.py          # @log_tool_execution decorator
│   └── exceptions.py
├── dct_client/client.py       # Async HTTP client with retry/backoff
├── tools/
│   ├── __init__.py            # Dynamic tool registration
│   ├── *_endpoints_tool.py    # Pre-built grouped tools
│   └── core/
│       ├── meta_tools.py           # Retained spec helpers (find_endpoint, get_spec_chunk)
│       ├── tool_factory.py         # Dynamic tool generation
│       ├── dynamic.py              # Dynamic mode: discovery + execute tools with FR-001–008 gate
│       ├── confirmation_token.py   # Single-use body-bound HMAC tokens
│       ├── confirmation_store.py   # ConsumedTokenStore + GrantStore (in-memory, TTL)
│       ├── confirmation_levels.py  # validate_elevated(), validate_manual(), build_required_fields()
│       ├── confirmation_resolver.py # check_confirmation_with_fallback(); velocity + grant routing
│       ├── audit.py                # Immutable local gate-event emitter
│       ├── floor_operations.py     # is_floor_operation() — always requires individual confirm
│       └── velocity_counter.py     # Sliding-window per-identity batch-check counter
└── toolsgenerator/driver.py   # OpenAPI spec processor
```

### Startup Flow

`main.py` → initialize `DCTAPIClient` → `register_all_tools()` (dynamic module discovery in `tools/__init__.py`) → FastMCP stdio transport. Shutdown: lifespan context manager closes HTTP client and ends telemetry session.

## Testing

See [`.claude/test/testing.md`](.claude/test/testing.md) for the full testing approach — manual MCP client testing and automated Docker pytest scripts. Test infrastructure setup (Docker build, credentials, env vars) is in [`.claude/test/test-infra.md`](.claude/test/test-infra.md).
