# Toolkit Resource: Versioned URIs and Async Cache Refresh — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register toolkit MCP resources by `name@version`, make `@log_tool_execution` support async tools, and refresh the toolkit cache after `upload_toolkit`/`delete_toolkit` completes.

**Architecture:** `@log_tool_execution` branches at decoration time using `inspect.iscoroutinefunction`. `toolkit_schemas.py` gains a `_refresh_state` hook and a `refresh_toolkit_cache()` async function registered at startup via `main.py`. `driver.py` generates `async def toolkit_tool` and emits `await refresh_toolkit_cache()` after confirmed upload/delete calls.

**Tech Stack:** Python 3.11+, FastMCP, pydantic AnyUrl, asyncio

---

## File Map

| File | Change |
|---|---|
| `src/dct_mcp_server/core/decorators.py` | Add `import inspect`; add async branch before sync wrapper |
| `src/dct_mcp_server/core/toolkit_schemas.py` | `name@version` key; `_registered_display_name_uris` set; `register_refresh_hook`; `refresh_toolkit_cache` |
| `src/dct_mcp_server/core/__init__.py` | Export `register_refresh_hook`, `refresh_toolkit_cache` |
| `src/dct_mcp_server/main.py` | Import and call `register_refresh_hook` after prefetch |
| `src/dct_mcp_server/toolsgenerator/driver.py` | `ACTIONS_REQUIRING_CACHE_REFRESH`; async signature; `_emit_api_return` helper; URI hint text |

---

### Task 1: Async branch in `@log_tool_execution`

**Files:**
- Modify: `src/dct_mcp_server/core/decorators.py`

- [ ] **Step 1: Add `import inspect` and the async wrapper branch**

Replace the entire contents of `src/dct_mcp_server/core/decorators.py` with:

```python
"""
This module contains decorators for use across the MCP server.
"""

import functools
import inspect

from dct_mcp_server.core.logging import get_logger
from dct_mcp_server.core.session import log_tool_call


def log_tool_execution(func):
    """
    A decorator to log the execution of a tool, including its name,
    arguments, and success or failure, to the session telemetry log.
    Supports both sync and async tool functions.
    """
    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            tool_name = func.__name__
            tool_data = {
                "tool_name": tool_name,
                "status": "unknown",
            }
            logger.info(f"Executing tool: {tool_name}")
            try:
                result = await func(*args, **kwargs)
                logger.info(f"Tool '{tool_name}' executed successfully.")
                tool_data["status"] = "success"
                log_tool_call(tool_data)
                return result
            except Exception as e:
                logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
                tool_data["status"] = "failure"
                tool_data["error"] = str(e)
                log_tool_call(tool_data)
                raise
        return wrapper

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        tool_name = func.__name__
        tool_data = {
            "tool_name": tool_name,
            "status": "unknown",
        }
        logger.info(f"Executing tool: {tool_name}")
        try:
            result = func(*args, **kwargs)
            logger.info(f"Tool '{tool_name}' executed successfully.")
            tool_data["status"] = "success"
            log_tool_call(tool_data)
            return result
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            tool_data["status"] = "failure"
            tool_data["error"] = str(e)
            log_tool_call(tool_data)
            raise

    return wrapper
```

- [ ] **Step 2: Verify server starts without errors**

```bash
cd /path/to/dxi-mcp-server
export DCT_API_KEY=dummy DCT_BASE_URL=http://localhost
python -c "from dct_mcp_server.core.decorators import log_tool_execution; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/dct_mcp_server/core/decorators.py
git commit -m "Support async functions in @log_tool_execution"
```

---

### Task 2: `name@version` keys, dedup set, and refresh hook in `toolkit_schemas.py`

**Files:**
- Modify: `src/dct_mcp_server/core/toolkit_schemas.py`

- [ ] **Step 1: Add module-level state variables**

After line 25 (`TOOLKIT_SCHEMAS_DIR = ...`), add:

```python
_registered_display_name_uris: set[str] = set()
_refresh_state: dict = {}
```

- [ ] **Step 2: Change `display_name_to_id` key to `name@version` in `fetch_and_cache_toolkit_schemas`**

Replace lines 71–78 (the `display_name` / `display_name_to_id` block):

```python
            display_name = (
                toolkit.get("display_name")
                or toolkit.get("pretty_name")
                or toolkit.get("name")
                or toolkit_id
            )
            version = toolkit.get("version", "")
            key = f"{display_name}@{version}" if version else display_name
            display_name_to_id[key] = toolkit_id
            logger.debug(f"Cached toolkit schema: {toolkit_id} (key={key})")
```

- [ ] **Step 3: Update `register_toolkit_resources` loop to handle `name@version` URIs and skip duplicates**

Replace the entire `# -- concrete resources keyed by display_name --` loop (lines 168–198) with:

```python
    # -- concrete resources keyed by display_name@version for prompt-driven discovery --
    registered = 0
    for key, toolkit_id in display_name_to_id.items():
        if "@" in key:
            display_part, version_part = key.rsplit("@", 1)
            safe_display = urllib.parse.quote(display_part, safe="-_.")
            safe_version = urllib.parse.quote(version_part, safe="-_.")
            uri_str = f"toolkit://{safe_display}@{safe_version}/schema"
            resource_name = (
                f"toolkit_schema_{safe_display}_{safe_version}"
                .replace(".", "_").replace("-", "_")
            )
            title_str = f"Toolkit: {display_part} v{version_part}"
        else:
            safe_name = urllib.parse.quote(key, safe="-_.")
            uri_str = f"toolkit://{safe_name}/schema"
            resource_name = f"toolkit_schema_{safe_name}"
            title_str = f"Toolkit: {key}"

        if uri_str in _registered_display_name_uris:
            logger.debug(f"Skipping already-registered MCP resource: {uri_str}")
            continue

        def _make_reader(tid: str):
            def _read() -> str:
                schema = get_cached_toolkit_schema(tid)
                if schema is None:
                    return json.dumps({"error": f"Toolkit '{tid}' not found in cache."})
                return json.dumps(schema, indent=2)
            return _read

        resource = FunctionResource(
            uri=AnyUrl(uri_str),
            name=resource_name,
            title=title_str,
            description=(
                f"Schema for toolkit '{key}'. Contains "
                f"virtual_source_definition, linked_source_definition, "
                f"discovery_definition, snapshot_parameters_definition, etc. "
                f"Read this before AppData link or provision operations when "
                f"the plugin type is known from context."
            ),
            mime_type="application/json",
            fn=_make_reader(toolkit_id),
        )
        app.add_resource(resource)
        _registered_display_name_uris.add(uri_str)
        registered += 1
        logger.debug(f"Registered MCP resource: {uri_str} -> {toolkit_id}")

    logger.info(f"Registered {registered} toolkit schema MCP resource(s) by display_name")
    return registered
```

- [ ] **Step 4: Add `register_refresh_hook` and `refresh_toolkit_cache` after `list_cached_toolkit_ids`**

```python
def register_refresh_hook(app, dct_client) -> None:
    """Store app and dct_client for use by refresh_toolkit_cache."""
    _refresh_state['app'] = app
    _refresh_state['dct_client'] = dct_client


async def refresh_toolkit_cache() -> None:
    """Re-fetch all toolkit schemas and re-register MCP resources. Non-fatal."""
    if not _refresh_state:
        return
    try:
        _, new_map = await fetch_and_cache_toolkit_schemas(_refresh_state['dct_client'])
        register_toolkit_resources(_refresh_state['app'], new_map)
        logger.info("Toolkit cache refreshed successfully")
    except Exception as e:
        logger.warning(f"Toolkit cache refresh failed: {e}")
```

- [ ] **Step 5: Smoke-check the module imports cleanly**

```bash
python -c "from dct_mcp_server.core.toolkit_schemas import register_refresh_hook, refresh_toolkit_cache; print('OK')"
```
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add src/dct_mcp_server/core/toolkit_schemas.py
git commit -m "Add name@version URIs, dedup set, and refresh hook to toolkit_schemas"
```

---

### Task 3: Export new names from `core/__init__.py`

**Files:**
- Modify: `src/dct_mcp_server/core/__init__.py`

- [ ] **Step 1: Add imports and `__all__` entries**

Replace the `toolkit_schemas` import block (lines 13–18) and the `__all__` list (lines 20–36) with:

```python
from .toolkit_schemas import (
    fetch_and_cache_toolkit_schemas,
    register_toolkit_resources,
    get_cached_toolkit_schema,
    list_cached_toolkit_ids,
    register_refresh_hook,
    refresh_toolkit_cache,
)

__all__ = [
    "get_logger",
    "setup_logging",
    "DCTClientError",
    "MCPError",
    "ToolError",
    "log_tool_execution",
    "start_session",
    "end_session",
    "get_session_logger",
    "log_tool_call",
    "get_current_session_id",
    "fetch_and_cache_toolkit_schemas",
    "register_toolkit_resources",
    "get_cached_toolkit_schema",
    "list_cached_toolkit_ids",
    "register_refresh_hook",
    "refresh_toolkit_cache",
]
```

- [ ] **Step 2: Verify**

```bash
python -c "from dct_mcp_server.core import register_refresh_hook, refresh_toolkit_cache; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/dct_mcp_server/core/__init__.py
git commit -m "Export register_refresh_hook and refresh_toolkit_cache from core"
```

---

### Task 4: Call `register_refresh_hook` in `main.py`

**Files:**
- Modify: `src/dct_mcp_server/main.py`

- [ ] **Step 1: Add `register_refresh_hook` to the import from `toolkit_schemas`**

Replace lines 31–34:

```python
from dct_mcp_server.core.toolkit_schemas import (
    fetch_and_cache_toolkit_schemas,
    register_toolkit_resources,
    register_refresh_hook,
)
```

- [ ] **Step 2: Call `register_refresh_hook` inside the prefetch `try` block**

In `async_main`, the prefetch block (lines 135–140) becomes:

```python
        try:
            _, display_name_to_id = await fetch_and_cache_toolkit_schemas(dct_client)
            register_toolkit_resources(app, display_name_to_id)
            register_refresh_hook(app, dct_client)
            logger.info("Toolkit schemas prefetched and registered as MCP resources")
        except Exception as e:
            logger.warning(f"Toolkit schema prefetch failed (non-fatal): {e}")
```

- [ ] **Step 3: Verify server starts**

```bash
python -c "from dct_mcp_server.main import main; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/dct_mcp_server/main.py
git commit -m "Register toolkit cache refresh hook at startup"
```

---

### Task 5: Async toolkit_tool generation in `driver.py`

**Files:**
- Modify: `src/dct_mcp_server/toolsgenerator/driver.py`

- [ ] **Step 1: Add `ACTIONS_REQUIRING_CACHE_REFRESH` constant after `ACTIONS_REQUIRING_TOOLKIT_SCHEMA`**

After line 86 (the closing `}` of `ACTIONS_REQUIRING_TOOLKIT_SCHEMA`), add:

```python
ACTIONS_REQUIRING_CACHE_REFRESH: set[str] = {"upload_toolkit", "delete_toolkit"}
```

- [ ] **Step 2: Update `_TOOLKIT_SCHEMA_HINT_COMMON` URI example**

Replace the `_TOOLKIT_SCHEMA_HINT_COMMON` string (lines 88–96):

```python
_TOOLKIT_SCHEMA_HINT_COMMON = (
    "IMPORTANT — Toolkit schema for AppData payloads: "
    "Do NOT call toolkit_tool to fetch the schema — it is already pre-cached as MCP resources.\n"
    "    Two lookup paths:\n"
    "      • Plugin type known from prompt (e.g. user said 'MySQL'): call list_resources, "
    "match by display_name@version (e.g. 'toolkit://mysql-plugin@2025.1.1/schema'), "
    "then read that resource URI.\n"
    "      • toolkit_id available from an existing VDB/dSource object: read "
    "toolkit://{toolkit_id}/schema directly via the template resource.\n"
)
```

- [ ] **Step 3: Add `_emit_api_return` helper function**

Add the following function just before `_generate_unified_tool` (line 588):

```python
def _emit_api_return(action_name: str, method: str, endpoint_var: str, extra_args: str = "") -> str:
    """Emit a return statement for an API call, with await refresh for cache-refresh actions."""
    call = f"make_api_request('{method}', {endpoint_var}, params=params{extra_args})"
    if action_name in ACTIONS_REQUIRING_CACHE_REFRESH:
        return (
            f"        result = {call}\n"
            f"        await refresh_toolkit_cache()\n"
            f"        return result\n"
        )
    return f"        return {call}\n"
```

- [ ] **Step 4: Make the function signature `async def` for tools with cache-refresh actions**

In `_generate_unified_tool`, replace line 776:

```python
    func_code = f"@log_tool_execution\ndef {tool_name}(\n"
```

with:

```python
    is_async = any(a in ACTIONS_REQUIRING_CACHE_REFRESH for a in action_details)
    func_kw = "async def" if is_async else "def"
    func_code = f"@log_tool_execution\n{func_kw} {tool_name}(\n"
```

- [ ] **Step 5: Replace the three `return make_api_request(...)` lines in the action dispatch with `_emit_api_return`**

In `_generate_unified_tool`, replace lines 1013–1039 (the `has_filter / POST / else` dispatch block) with:

```python
        # Handle request body
        if details["has_filter"] and method == "POST":
            func_code += "        body = {'filter_expression': filter_expression} if filter_expression else {}\n"
            func_code += _emit_api_return(action_name, method, endpoint_var, ", json_body=body")
        elif method in ["POST", "PUT", "PATCH"]:
            # Collect body params - use the body_params stored in action_details
            body_params = details.get("body_params", [])
            if body_params:
                # Build body dict with original API names as keys and snake_case vars as values
                body_items = ", ".join([
                    f"'{orig}': {snake}"
                    for orig, snake, is_json in body_params
                ])
                body_param_names = {snake for _, snake, _ in body_params}
                if "environment_user_id" in body_param_names:
                    func_code += "        if not environment_user_id:\n"
                    func_code += "            environment_user_id = environment_user_ref or environment_user\n"
                func_code += f"        body = {{k: v for k, v in {{{body_items}}}.items() if v is not None}}\n"
                func_code += _emit_api_return(action_name, method, endpoint_var, ", json_body=body if body else None")
            else:
                func_code += _emit_api_return(action_name, method, endpoint_var)
        else:
            func_code += _emit_api_return(action_name, method, endpoint_var)
```

- [ ] **Step 6: Add the conditional `refresh_toolkit_cache` import in `generate_tools_from_openapi`**

In `generate_tools_from_openapi`, after `tool_file_content = prefix` (line 495), add:

```python
        # Add refresh import only for modules whose tools include cache-refresh actions
        needs_refresh = any(
            api["action"] in ACTIONS_REQUIRING_CACHE_REFRESH
            for apis_list in tools.values()
            for api in apis_list
        )
        if needs_refresh:
            tool_file_content += "from dct_mcp_server.core.toolkit_schemas import refresh_toolkit_cache\n"
```

- [ ] **Step 7: Verify driver.py imports cleanly**

```bash
python -c "from dct_mcp_server.toolsgenerator.driver import generate_tools_from_openapi; print('OK')"
```
Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add src/dct_mcp_server/toolsgenerator/driver.py
git commit -m "Generate async toolkit_tool with cache refresh after upload/delete"
```

---

### Task 6: Manual end-to-end verification

- [ ] **Step 1: Start server against a live DCT instance**

```bash
export DCT_API_KEY=<your-key>
export DCT_BASE_URL=<your-dct-url>
./start_mcp_server_uv.sh
```

- [ ] **Step 2: Connect Claude Desktop (or Cursor), call `list_resources`**

Expected: resources include versioned URIs like `toolkit://mysql-plugin@2025.1.1/schema` (not just `toolkit://mysql-plugin/schema`). Multiple entries if the DCT instance has the same plugin on multiple engines with the same version will still collapse — one per unique `name@version` pair is correct.

- [ ] **Step 3: Read a versioned resource**

Ask the AI: `read the resource toolkit://mysql-plugin@<version>/schema`

Expected: returns the full toolkit JSON with `virtual_source_definition`, `linked_source_definition`, etc.

- [ ] **Step 4: Verify cache refresh after delete (if safe to do on the test instance)**

Call `toolkit_tool(action='delete_toolkit', toolkit_id='<id>', confirmed=True)`. Then call `list_resources`. The deleted toolkit's display_name@version URI should now return `{"error": "not found in cache"}` when read, and no new entry for it appears (old registration stays, file is gone).

- [ ] **Step 5: Verify async telemetry logging**

Check `logs/dct_mcp_server.log` after a `toolkit_tool` call. Confirm lines like:
```
Executing tool: toolkit_tool
Tool 'toolkit_tool' executed successfully.
```

---

## Spec Coverage Check

| Spec requirement | Task |
|---|---|
| `name@version` key in `fetch_and_cache_toolkit_schemas` | Task 2, Step 2 |
| `_registered_display_name_uris` dedup set | Task 2, Step 3 |
| URI format `toolkit://name@version/schema` | Task 2, Step 3 |
| `register_refresh_hook` + `refresh_toolkit_cache` | Task 2, Step 4 |
| `core/__init__.py` exports | Task 3 |
| `main.py` calls `register_refresh_hook` | Task 4 |
| `@log_tool_execution` async branch | Task 1 |
| `ACTIONS_REQUIRING_CACHE_REFRESH` | Task 5, Step 1 |
| URI hint text updated | Task 5, Step 2 |
| `async def toolkit_tool` generated | Task 5, Step 4 |
| `await refresh_toolkit_cache()` emitted after upload/delete | Task 5, Steps 3+5 |
| Conditional import in generated file | Task 5, Step 6 |
