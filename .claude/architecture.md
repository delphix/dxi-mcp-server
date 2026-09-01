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
    │       ├── tools/core/meta_tools.py          ← Retained spec helpers (find_endpoint, get_spec_chunk)
    │       ├── tools/core/tool_factory.py         ← Runtime tool generation from OpenAPI spec
    │       ├── tools/core/dynamic.py              ← Dynamic mode: discovery + execute + FR-001–008 gate
    │       ├── tools/core/confirmation_token.py   ← Single-use body-bound HMAC tokens + ConsumedTokenStore
    │       ├── tools/core/confirmation_store.py   ← ConsumedTokenStore + GrantStore (in-memory, TTL)
    │       ├── tools/core/confirmation_levels.py  ← validate_elevated(), validate_manual(), build_required_fields()
    │       ├── tools/core/confirmation_resolver.py← check_confirmation_with_fallback(); velocity + grant routing
    │       ├── tools/core/audit.py                ← Immutable gate-event emitter (7 outcomes)
    │       ├── tools/core/floor_operations.py     ← is_floor_operation(); non-bypassable operations
    │       ├── tools/core/velocity_counter.py     ← Sliding-window per-identity batch-check counter
    │       └── tools/*_endpoints_tool.py          ← Pre-built grouped tools (fallback)
    ├── config/config.py             ← Env var loading and validation
    ├── config/loader.py             ← Toolset + confirmation rule parsing (lru_cache'd)
    │       ├── config/toolsets/*.txt              ← Persona toolset definitions
    │       ├── config/mappings/manual_confirmation.txt
    │       ├── config/mappings/floor_operations.txt  ← Patterns for non-bypassable operations
    │       └── config/mappings/read_exclusions.txt   ← POSTs excluded from keyword fallback
    ├── dct_client/client.py         ← Async httpx client with retry/backoff
    ├── testing/cli.py               ← dct-mcp-test CLI — test runner wrapping pytest with layer routing
    └── core/
            ├── logging.py           ← setup_logging(), get_logger(), rotating file handler
            ├── session.py           ← Telemetry session management; mints PROCESS_IDENTITY at startup
            ├── decorators.py        ← @log_tool_execution (apply to all tool functions)
            └── exceptions.py        ← DCTClientError, MCPError
```

---

## Toolset Modes

### Fixed Mode (`DCT_TOOLSET=<name>`)
- Pre-registers all tools for the toolset at startup
- Tools loaded from `$TEMP/dct_mcp_tools/` (generated) first, then `tools/*_endpoints_tool.py` (pre-built)
- Available toolsets: `self_service` (default), `self_service_provision`, `continuous_data_admin`, `platform_admin`, `reporting_insights`

### Dynamic Mode (`DCT_TOOLSET=dynamic`, default)
- Registers exactly two tools — `discovery` and `execute` — driven by the live OpenAPI spec (`spec_cache.py`)
- No per-endpoint tool registration; the AI browses and calls the API through the two tools

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
1. tool(action="delete", id="x")                              → returns confirmation_required + token
2. tool(action="delete", id="x", confirmation_token="<tok>")  → verifies token, executes
```

Rules in `config/mappings/manual_confirmation.txt`:
```
METHOD|path_pattern|confirmation_level|message_template
```

Levels: `standard`, `elevated`, `manual`, `retention_check:N`, `policy_impact_check:N`, `batch_check:N:T`

**Hardened in DLPXECO-14458** (confirmation-system strengthening):
- **Single-use body-bound tokens** — HMAC includes `canonical_json(body)`; tokens consumed on use (no replay)
- **Differentiated levels** — `elevated` requires `confirmed_resource_name`; `manual` adds `acknowledged_impact=True`
- **Floor operations** — any DELETE or POST to `*/delete` cannot be bypassed by grants (`floor_operations.txt`)
- **Batch grants** — `GrantStore` lets one user approval cover N enumerated calls; floor ops excluded
- **MCP elicitation** — `Context.elicit()` used when client supports it; `DCT_CONFIRMATION_ENFORCEMENT=strict` refuses non-elicitation clients
- **Per-identity velocity** — `batch_check:N:T` keyed on `(PROCESS_IDENTITY, method, path_template)`
- **Audit events** — `audit.py` emits 7 outcomes (`required`, `approved`, `refused`, `expired`, `replay_rejected`, `grant_covered`, `batch_triggered`) always, regardless of telemetry opt-in

---

## Dynamic Tool Generation

At startup, `main()` calls `generate_tools_from_openapi()` before registering tools:

1. Downloads `{DCT_BASE_URL}/dct/static/api-external.yaml`
2. Processes spec into grouped tool modules
3. Writes to `$TEMP/dct_mcp_tools/`
4. Falls back to bundled `docs/api-external.yaml` on download failure

Generated modules take priority over pre-built `*_endpoints_tool.py` files. Failure is non-fatal.

---

## MCP Configuration (`.mcp.json`)

The `.mcp.json` file defines how Claude Code connects to the DCT MCP server and other supporting servers:

```json
{
  "mcpServers": {
    "delphix-dct": {
      "command": "python",
      "args": ["-m", "dct_mcp_server.main"],
      "env": {
        "DCT_API_KEY": "${DCT_API_KEY}",
        "DCT_BASE_URL": "${DCT_BASE_URL}",
        "DCT_TOOLSET": "${DCT_TOOLSET:-continuous_data_admin}",
        ...
      }
    }
  }
}
```

Credentials are loaded from `.claude/settings.local.json` at runtime — the `${VAR}` syntax is resolved by Claude's MCP client config loader, not by the server itself.

## Testing Infrastructure

### `testing/cli.py` — dct-mcp-test CLI

Entry point: `dct-mcp-test` (from `project.scripts` in `pyproject.toml`).

Provides a unified test runner for multiple layers:
- `--layer unit` — unit tests only
- `--layer integration` — integration tests
- `--layer functional` — functional tests
- `--layer ci` — unit + integration + functional (merge-gate suite, no DCT credentials needed)
- `--layer e2e` — end-to-end tests against a real DCT instance
- `--layer llm` — Layer 5 LLM-driven tests via Claude Code CLI
- `--layer scenarios` — subset of LLM tests for scenario execution
- `--layer all` — all layers except `llm`

Usage:
```bash
dct-mcp-test --layer ci                    # Run CI suite locally
dct-mcp-test --layer e2e --api-key ABC     # Run E2E tests
dct-mcp-test remote --layer llm            # Run Layer 5 tests against remote DCT
```

## Key Platform Behaviors

- **API key prefix**: `DCTAPIClient` prepends `apk ` automatically — do not prefix in env vars
- **SSL**: Defaults to `verify=false` — set `DCT_VERIFY_SSL=true` in production
- **Retries**: Exponential backoff up to `DCT_MAX_RETRIES` (default 3) on transient failures
- **Toolset config cache**: `loader.py` uses `@lru_cache` — call `clear_cache()` if `.txt` files change at runtime
- **Telemetry**: Opt-in only (`IS_LOCAL_TELEMETRY_ENABLED=true`); session logs written to `logs/sessions/{id}.log`
