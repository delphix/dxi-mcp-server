# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Package Overview

`src/dct_mcp_server/` is the single Python package. All source lives here. Subpackages with their own CLAUDE.md:
- `config/` — toolset `.txt` files and confirmation rules (no code changes needed for new endpoints)
- `tools/` — MCP tool implementations and dynamic tool registration

## `main.py` — Entry Point

Startup sequence in `main()`:
1. `generate_tools_from_openapi()` — attempts to generate fresh tools from DCT API; failure is non-fatal, falls back to pre-built tools
2. `async_main()` → creates `DCTAPIClient` → calls `register_all_tools(app, dct_client)` → starts FastMCP on stdio transport

The `FastMCP` app is a module-level global (`app`). The `lifespan` async context manager handles startup/shutdown: starts telemetry session if `IS_LOCAL_TELEMETRY_ENABLED=true`, closes the HTTP client on exit.

## `core/` — Infrastructure

| File | Purpose |
|---|---|
| `logging.py` | `setup_logging()` initializes rotating file handler at `logs/dct_mcp_server.log`. Use `get_logger(__name__)` everywhere — never `logging.getLogger` directly. |
| `session.py` | `start_session()` / `end_session()` / `log_tool_call()` — writes JSON telemetry to `logs/sessions/{id}.log`. Off by default. |
| `decorators.py` | `@log_tool_execution` — wraps every tool function; logs execution start/end and records success/failure to the telemetry session. Apply to all tool functions. |
| `exceptions.py` | `DCTClientError`, `MCPError` — raise these rather than bare exceptions in client/tool code. |

## `dct_client/client.py` — HTTP Client

`DCTAPIClient` is an async httpx client. Key details:
- Prepends `apk ` to the API key in the `Authorization` header automatically — do not add the prefix in env vars
- `make_request(method, endpoint, ...)` handles retries with exponential backoff up to `DCT_MAX_RETRIES`
- The client is a long-lived singleton created once in `main.py` and passed to every `register_tools()` call
- `endpoint` is the DCT path (e.g. `/vdbs/{vdbId}`) — the base URL and `/dct` prefix are added internally

## `toolsgenerator/driver.py` — OpenAPI Tool Generator

`generate_tools_from_openapi()` is called at startup before tool registration. It downloads `{DCT_BASE_URL}/dct/static/api-external.yaml`, processes it, and writes generated tool modules to `$TEMP/dct_mcp_tools/`. These take priority over pre-built `*_endpoints_tool.py` files. Falls back to the bundled `docs/api-external.yaml` if the download fails.
