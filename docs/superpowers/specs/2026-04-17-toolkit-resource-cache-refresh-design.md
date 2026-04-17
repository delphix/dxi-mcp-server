# Toolkit Resource: Versioned URIs and Async Cache Refresh — Design Spec

**Date:** 2026-04-17
**Status:** Approved for implementation

---

## Background

The toolkit schema caching system (see `2026-04-17-toolkit-schema-caching-design.md`) registers MCP resources at startup so the AI can read plugin schemas without extra API round-trips. Three gaps remain:

1. `display_name_to_id` is keyed by `display_name` only — multiple versions of the same plugin (across engines) collapse to one entry, so `list_resources` shows only one URI per plugin type instead of one per version.
2. `upload_toolkit` and `delete_toolkit` do not refresh the cache after success — MCP resources stay stale for the rest of the session.
3. `@log_tool_execution` is sync-only — making any tool async would silently break telemetry logging.

---

## Design

### 1. `name@version` URI scheme (`core/toolkit_schemas.py`)

**Problem:** `display_name_to_id[display_name] = toolkit_id` overwrites earlier entries when the same plugin name appears across engines or versions.

**Fix:** Key the dict by `display_name@version` when a version field is present:

```python
version = toolkit.get("version", "")
key = f"{display_name}@{version}" if version else display_name
display_name_to_id[key] = toolkit_id
```

**URI construction:** Display name and version are URL-encoded separately; `@` is kept literal in the authority section (valid per RFC 3986):

```
toolkit://mysql-plugin@2025.1.1/schema
toolkit://Unstructured%20Files/schema      # no version → unchanged
```

**Deduplication on re-registration:** Add a module-level `_registered_display_name_uris: set[str]`. In `register_toolkit_resources`, skip `add_resource` for any URI already in the set. This prevents errors when the function is called again after a cache refresh. Deleted toolkit resources remain registered but their closure returns `{"error": "not found in cache"}` — same behaviour as the template resource for unknown IDs.

---

### 2. Async refresh hook (`core/toolkit_schemas.py` + `main.py`)

**Problem:** After `upload_toolkit` or `delete_toolkit` succeeds, the cache is stale. The fix requires calling the async `fetch_and_cache_toolkit_schemas`, but the toolkit tool function cannot directly hold references to `app` and `dct_client`.

**Fix:** Expose a hook in `toolkit_schemas.py` that stores those references at startup:

```python
_refresh_state: dict = {}

def register_refresh_hook(app, dct_client) -> None:
    _refresh_state['app'] = app
    _refresh_state['dct_client'] = dct_client

async def refresh_toolkit_cache() -> None:
    """Refresh cache and re-register resources. Non-fatal."""
    if not _refresh_state:
        return
    try:
        _, new_map = await fetch_and_cache_toolkit_schemas(_refresh_state['dct_client'])
        register_toolkit_resources(_refresh_state['app'], new_map)
    except Exception as e:
        logger.warning(f"Toolkit cache refresh failed: {e}")
```

`main.py` calls `register_refresh_hook(app, dct_client)` immediately after the initial `fetch_and_cache_toolkit_schemas` call.

**Refresh is blocking:** the tool awaits `refresh_toolkit_cache()` before returning, so the AI sees updated resources immediately.

**Refresh only fires after confirmed execution.** The confirmation gate (`if conf: return conf`) exits early — the refresh call is placed after the API request, not before.

---

### 3. `@log_tool_execution` async support (`core/decorators.py`)

**Problem:** The decorator wraps with `def wrapper` — if applied to an `async def` tool, the function is no longer a coroutine and FastMCP cannot await it.

**Fix:** Branch at decoration time using `inspect.iscoroutinefunction`:

```python
import inspect

def log_tool_execution(func):
    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # identical logging/telemetry logic, with await
            result = await func(*args, **kwargs)
            ...
            return result
        return wrapper
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # existing sync logic unchanged
        ...
    return wrapper
```

The branch happens once at import time. All existing sync tools are unaffected.

---

### 4. `driver.py` — async toolkit_tool + hook call + URI hints

Add a set of actions that require cache refresh after success:

```python
ACTIONS_REQUIRING_CACHE_REFRESH: set[str] = {"upload_toolkit", "delete_toolkit"}
```

For toolkit_tool generation:
- Emit `async def toolkit_tool(...)` (not `def`)
- Import `refresh_toolkit_cache` from `dct_mcp_server.core.toolkit_schemas`
- After the confirmed API request for any action in `ACTIONS_REQUIRING_CACHE_REFRESH`, emit `await refresh_toolkit_cache()`

Update the `_TOOLKIT_SCHEMA_HINT_COMMON` URI example to reflect the versioned format:

```
• Plugin type known from prompt (e.g. user said 'MySQL'): call list_resources,
  match by display_name@version (e.g. 'toolkit://mysql-plugin@2025.1.1/schema'),
  then read that resource URI.
```

The pre-built `tools/environment_endpoints_tool.py` and `tools/dataset_endpoints_tool.py` are regenerated from `driver.py` — not hand-edited.

---

## Files Changed

| File | How |
|---|---|
| `core/decorators.py` | Manual — async branch in `@log_tool_execution` |
| `core/toolkit_schemas.py` | Manual — `name@version` key, `_registered_display_name_uris`, `register_refresh_hook`, `refresh_toolkit_cache` |
| `main.py` | Manual — `register_refresh_hook(app, dct_client)` call after prefetch |
| `toolsgenerator/driver.py` | Manual — async toolkit_tool, `ACTIONS_REQUIRING_CACHE_REFRESH`, hook call, URI hints |

---

## Testing

| Scenario | Verification |
|---|---|
| `list_resources` shows `toolkit://mysql-plugin@2025.1.1/schema` | Connect Claude Desktop, call `list_resources`, confirm versioned URIs appear |
| Same plugin on multiple engines → multiple URIs | Confirm one resource per unique `display_name@version` pair |
| Plugin with no version field → unchanged URI `toolkit://mysql-plugin/schema` | Confirm fallback works |
| `upload_toolkit` refreshes cache without restart | Upload a toolkit, confirm new resource appears in `list_resources` immediately |
| `delete_toolkit` cache returns "not found" | Delete a toolkit, read its former URI, confirm `{"error": "not found in cache"}` |
| Async tool telemetry logged correctly | Execute toolkit_tool, confirm telemetry session log records success/failure |
| Existing sync tools unaffected | Run a non-async tool, confirm `@log_tool_execution` behaves identically |
