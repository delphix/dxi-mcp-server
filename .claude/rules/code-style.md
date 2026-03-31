# Code Style Rules

## Language and Runtime

- Python 3.11+
- Async-first: tool registration and DCT client are async; tool functions themselves are sync (wrapped by `@log_tool_execution`)

## Exception Handling

Use `DCTClientError` for HTTP/connection failures and `MCPError` for MCP-layer errors. Both are in `src/dct_mcp_server/core/exceptions.py`. Never raise bare `Exception` in tool or client code.

## Logging

Always use `get_logger(__name__)` from `dct_mcp_server.core.logging` — never `logging.getLogger` directly:

```python
from dct_mcp_server.core.logging import get_logger
logger = get_logger(__name__)
```

## Tool Functions

Every tool function must be decorated with `@log_tool_execution` from `dct_mcp_server.core.decorators`. This handles telemetry logging and error recording automatically:

```python
from dct_mcp_server.core.decorators import log_tool_execution

@app.tool()
@log_tool_execution
def my_tool(action: str, ...):
    ...
```

## Grouped Tool Pattern

New tools must follow the grouped action pattern — one tool function handles multiple related endpoints via an `action` parameter. Action names must exactly match entries in the corresponding `config/toolsets/*.txt` file.

## Shell Command Templates

Do not inline DCT API paths as raw strings in tool functions. Paths come from the toolset `.txt` config files and are resolved through `config/loader.py`.

## Code Organisation

| Layer | Path | Rule |
|-------|------|------|
| Entry point | `main.py` | Startup/shutdown only — no business logic |
| Tool registration | `tools/__init__.py` | Discovery and loading only |
| Tool implementations | `tools/*_endpoints_tool.py` | Grouped tools, one file per resource domain |
| Auto mode | `tools/core/meta_tools.py` | Only registered when `DCT_TOOLSET=auto` |
| Dynamic generation | `tools/core/tool_factory.py` | Runtime tool generation from OpenAPI spec |
| Config loading | `config/loader.py` | All toolset and confirmation parsing |
| HTTP client | `dct_client/client.py` | All DCT API calls go through `DCTAPIClient` |
| Infrastructure | `core/` | Logging, session, decorators, exceptions |
