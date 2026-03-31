# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Tools Directory

This directory contains MCP tool implementations. Each `*_endpoints_tool.py` file is a **pre-built grouped tool module** that serves as a fallback when dynamic generation fails.

### Adding a New Pre-built Tool Module

Every tool module must expose a `register_tools(app, dct_client)` function — this is the only contract the dynamic loader (`tools/__init__.py`) checks for. The loader auto-discovers any module in this directory that defines it.

```python
def register_tools(app, dct_client):
    @app.tool()
    @log_tool_execution
    def my_resource_tool(action: str, ...):
        ...
```

### Grouped Tool Pattern

Each file groups related DCT API endpoints under one MCP tool with an `action` parameter. The `action` values must exactly match the action names in the corresponding toolset `.txt` config file.

Example mapping:
```
# In config/toolsets/self_service.txt:
POST|/vdbs/search|search        ← action="search"
GET|/vdbs/{vdbId}|get           ← action="get"

# In dataset_endpoints_tool.py:
def vdb_tool(action: str, ...):
    if action == "search": ...
    elif action == "get": ...
```

### Tool-to-Module Mapping

When adding a new tool, register it in `config/loader.py:get_modules_for_toolset()` inside `TOOL_TO_MODULE`. Without this, the loader cannot filter which modules to load for a given toolset.

```python
"my_new_tool": "my_new_endpoints_tool",
```

### `core/` Subdirectory

- `meta_tools.py` — 5 meta-tools for `auto` mode only (`list_available_toolsets`, `get_toolset_tools`, `enable_toolset`, `disable_toolset`, `check_operation_confirmation`). Do not register these in fixed-toolset mode.
- `tool_factory.py` — Generates tool functions at runtime from the OpenAPI spec. Downloads spec from `{DCT_BASE_URL}/dct/static/api-external.yaml`; falls back to `docs/api-external.yaml`. Generated tools are cached in `$TEMP/dct_mcp_tools/` and take priority over pre-built modules.
