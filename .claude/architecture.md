# Architecture Reference

## What This Is

A Model Context Protocol (MCP) server that exposes Delphix Data Control Tower (DCT) API capabilities as structured tools for AI assistants (Claude, Cursor, VS Code Copilot, etc.).

- **Package**: `dct-mcp-server`
- **Transport**: stdio (MCP standard)
- **Framework**: FastMCP 2.13.2+
- **Language**: Python 3.11+

---

## Layer Map

```
main.py                              ← Entry point; FastMCP app, lifespan, startup/shutdown
    ├── toolsgenerator/driver.py     ← Generates tool modules from OpenAPI spec at startup
    ├── tools/__init__.py            ← Dynamic tool registration (priority: generated → pre-built)
    │       ├── tools/core/meta_tools.py      ← 5 meta-tools for auto mode only
    │       ├── tools/core/tool_factory.py    ← Runtime tool generation from OpenAPI spec
    │       └── tools/*_endpoints_tool.py     ← Pre-built grouped tools (fallback)
    ├── config/config.py             ← Env var loading and validation
    ├── config/loader.py             ← Toolset + confirmation rule parsing (lru_cache'd)
    │       ├── config/toolsets/*.txt          ← Persona toolset definitions
    │       └── config/mappings/manual_confirmation.txt
    ├── dct_client/client.py         ← Async httpx client with retry/backoff
    └── core/
            ├── logging.py           ← setup_logging(), get_logger(), rotating file handler
            ├── session.py           ← Telemetry session management
            ├── decorators.py        ← @log_tool_execution (apply to all tool functions)
            └── exceptions.py        ← DCTClientError, MCPError
```

---

## Toolset Modes

### Fixed Mode (`DCT_TOOLSET=<name>`)
- Pre-registers all tools for the toolset at startup
- Tools loaded from `$TEMP/dct_mcp_tools/` (generated) first, then `tools/*_endpoints_tool.py` (pre-built)
- Available toolsets: `self_service` (default), `self_service_provision`, `continuous_data_admin`, `platform_admin`, `reporting_insights`

### Auto Mode (`DCT_TOOLSET=auto`)
- Starts with 5 meta-tools only
- AI dynamically enables toolsets at runtime via `enable_toolset()` — no restart needed
- Uses `tools/list_changed` MCP notification to signal tool list updates to clients
- Not all clients support hot-switching (VS Code Copilot requires chat restart)

---

## Grouped Tools Pattern

Each `*_endpoints_tool.py` groups related DCT API endpoints under one MCP tool with an `action` parameter.

```
vdb_tool(action="search")    → POST /vdbs/search
vdb_tool(action="get")       → GET  /vdbs/{vdbId}
vdb_tool(action="refresh")   → POST /vdbs/{vdbId}/refresh_by_timestamp
```

Action names are defined in `config/toolsets/*.txt`. The implementation and the config must stay in sync.

---

## Confirmation System

Destructive operations use a two-step call pattern:

```
1. tool(action="delete", id="x")          → returns confirmation_required
2. tool(action="delete", id="x", confirmed=True)  → executes
```

Rules in `config/mappings/manual_confirmation.txt`:
```
METHOD|path_pattern|confirmation_level|message_template
```

Levels: `standard`, `elevated`, `manual`, `retention_check:N`, `policy_impact_check:N`

---

## Dynamic Tool Generation

At startup, `main()` calls `generate_tools_from_openapi()` before registering tools:

1. Downloads `{DCT_BASE_URL}/dct/static/api-external.yaml`
2. Processes spec into grouped tool modules
3. Writes to `$TEMP/dct_mcp_tools/`
4. Falls back to bundled `docs/api-external.yaml` on download failure

Generated modules take priority over pre-built `*_endpoints_tool.py` files. Failure is non-fatal.

---

## Key Platform Behaviors

- **API key prefix**: `DCTAPIClient` prepends `apk ` automatically — do not prefix in env vars
- **SSL**: Defaults to `verify=false` — set `DCT_VERIFY_SSL=true` in production
- **Retries**: Exponential backoff up to `DCT_MAX_RETRIES` (default 3) on transient failures
- **Toolset config cache**: `loader.py` uses `@lru_cache` — call `clear_cache()` if `.txt` files change at runtime
- **Telemetry**: Opt-in only (`IS_LOCAL_TELEMETRY_ENABLED=true`); session logs written to `logs/sessions/{id}.log`
