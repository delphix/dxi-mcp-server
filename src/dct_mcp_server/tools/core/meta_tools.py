"""
Meta-tools for DCT MCP Server toolset discovery and selection.

These tools are available in "auto" mode (DCT_TOOLSET=auto) and allow
the LLM to dynamically discover and work with available toolsets.

Meta-tools (8):
- list_available_toolsets: List all available toolsets with descriptions
- get_toolset_tools: Get detailed list of tools in a specific toolset
- enable_toolset: Enable a toolset at runtime (no restart required)
- disable_toolset: Disable current toolset, return to auto mode
- check_operation_confirmation: Check if operation needs confirmation
- execute_action: Execute any DCT action directly without tool list refresh
- find_endpoint: Fuzzy-match user intent against the OpenAPI spec
- get_spec_chunk: Resolve a $ref pointer from the cached OpenAPI spec

Runtime Registration Pattern (GitHub MCP Server style):
- Pre-load all tool modules into ToolInventory at startup
- enable_toolset() registers tools at runtime via app.add_tool()
- disable_toolset() unregisters via app.local_provider.remove_tool()
- FastMCP auto-sends tools/list_changed notification
"""

import logging
import re
from typing import Dict, Any, List, Optional, Callable

from mcp.server.fastmcp import Context
from dct_mcp_server.config import (
    get_available_toolsets,
    load_toolset_metadata,
    load_all_toolsets_metadata,
    get_tools_for_toolset,
    get_confirmation_for_operation,
    get_modules_for_toolset,
    load_toolset_grouped_apis,
)
from dct_mcp_server.core.decorators import log_tool_execution
from .tool_factory import (
    initialize_openapi_cache,
    register_toolset_tools,
    get_cached_spec,
)
from .endpoint_discovery import (
    build_corpus_from_spec,
    extract_hot_keywords_from_spec,
    rank_candidates,
)

HARD_LIMIT = 25

logger = logging.getLogger(__name__)


# Global state for runtime toolset switching
_app = None  # FastMCP app instance
_dct_client = None  # DCT API client instance
_tool_inventory: Dict[str, Dict[str, Any]] = {}  # Pre-loaded tool modules per toolset
_current_toolset: Optional[str] = None  # Currently active toolset (None = meta-tools only)
_registered_tool_names: List[str] = []  # Names of currently registered domain tools


def initialize_tool_inventory(app, dct_client):
    """
    Initialize the tool inventory for runtime tool switching.

    Called once at server startup to prepare for dynamic tool generation.
    Uses the dynamic tool factory pattern - no pre-generated files needed.

    Args:
        app: FastMCP application instance
        dct_client: DCT API client instance
    """
    global _app, _dct_client, _tool_inventory
    _app = app
    _dct_client = dct_client

    logger.info("Initializing tool inventory for runtime switching...")

    # Initialize OpenAPI spec cache for dynamic tool generation
    spec_loaded = initialize_openapi_cache(dct_client)
    if spec_loaded:
        logger.info("OpenAPI spec cached successfully for dynamic tool generation")
    else:
        logger.warning("OpenAPI spec not available - tools will have basic docstrings")

    # Get available toolsets from config
    available_toolsets = get_available_toolsets()

    # Mark all toolsets as available for dynamic generation
    for toolset_name in available_toolsets:
        _tool_inventory[toolset_name] = {
            "dynamic": True,
            "loaded": False,
        }

    logger.info(f"Tool inventory initialized with {len(_tool_inventory)} toolsets (dynamic generation)")


@log_tool_execution
def list_available_toolsets() -> Dict[str, Any]:
    """
    List all available toolsets with their descriptions and tool counts.

    Use this tool to discover what toolsets are available for the DCT MCP Server.
    Each toolset is designed for a specific persona or use case:

    - self_service: Basic VDB operations for developers and QA engineers
    - self_service_provision: Extended self-service with VDB provisioning capabilities
    - continuous_data_admin: Full DBA/Continuous Data admin operations
    - platform_admin: System administration and platform management
    - reporting_insights: Read-only reporting and analytics

    Returns:
        Dict containing:
        - toolsets: List of toolset information (name, description, tool_count)
        - total_count: Total number of available toolsets
        - instructions: How to get more details or enable a toolset
    """
    try:
        toolsets_metadata = load_all_toolsets_metadata()

        toolsets_list = []
        for name, metadata in sorted(toolsets_metadata.items()):
            toolsets_list.append({
                "name": name,
                "description": metadata.get("description", "No description available"),
                "tool_count": metadata.get("tool_count", 0),
                "primary_use_case": metadata.get("primary_use_case", "General use"),
            })

        return {
            "toolsets": toolsets_list,
            "total_count": len(toolsets_list),
            "instructions": (
                "For a single user-intent request, prefer 'find_endpoint' first — it fuzzy-matches "
                "the user's query against the OpenAPI spec and returns the best endpoint(s) with a "
                "suggested_toolset hint. Use 'get_spec_chunk' to resolve $ref pointers (parameters, "
                "schemas) on demand. Otherwise use 'get_toolset_tools' to browse a toolset, "
                "'enable_toolset' to register domain tools, or 'execute_action' to call any action "
                "directly without enabling a toolset."
            ),
        }
    except Exception as e:
        logger.error(f"Error listing toolsets: {e}")
        return {"error": str(e), "toolsets": [], "total_count": 0}


@log_tool_execution
def get_toolset_tools(toolset_name: str) -> Dict[str, Any]:
    """
    Get detailed information about tools available in a specific toolset.

    This tool provides a complete list of tools and their actions for a given toolset.
    Use this after 'list_available_toolsets' to explore a toolset in detail before
    calling 'enable_toolset' or 'execute_action'.

    Args:
        toolset_name: Name of the toolset (e.g., "self_service", "platform_admin")

    Returns:
        Dict containing:
        - toolset_name: The requested toolset name
        - metadata: Toolset metadata (description, use case)
        - tools: List of tools with their actions and descriptions
        - total_tools: Total number of tools in this toolset
        - instructions: How to enable this toolset or execute actions directly
    """
    try:
        available = get_available_toolsets()
        if toolset_name not in available:
            return {
                "error": f"Unknown toolset: {toolset_name}",
                "available_toolsets": available,
                "instructions": "Use one of the available toolset names",
            }

        metadata = load_toolset_metadata(toolset_name)
        tools = get_tools_for_toolset(toolset_name)

        return {
            "toolset_name": toolset_name,
            "metadata": {
                "description": metadata.get("description", "No description"),
                "primary_use_case": metadata.get("primary_use_case", "General use"),
            },
            "tools": tools,
            "total_tools": len(tools),
            "total_actions": sum(len(t.get("actions", [])) for t in tools),
            "instructions": (
                f"Call enable_toolset(toolset_name='{toolset_name}') to register all domain tools "
                f"at runtime (no restart required), or use execute_action(toolset_name='{toolset_name}', "
                f"tool_name=<tool>, action=<action>) to call any action directly."
            ),
        }
    except Exception as e:
        logger.error(f"Error getting toolset tools: {e}")
        return {"error": str(e)}


@log_tool_execution
async def enable_toolset(toolset_name: str, ctx: Context) -> Dict[str, Any]:
    """
    Enable a toolset at runtime - NO SERVER RESTART REQUIRED.

    This tool dynamically registers the tools for the specified toolset.
    The LLM's available tools will be updated immediately via the MCP
    tools/list_changed notification.

    If another toolset is currently active, it will be disabled first.

    Args:
        toolset_name: Name of the toolset to enable

    Returns:
        Dict containing:
        - toolset_name: The enabled toolset
        - status: "enabled" or "error"
        - tools_registered: Number of tools now available
        - previous_toolset: Previously active toolset (if any)
    """
    global _current_toolset, _registered_tool_names

    try:
        available = get_available_toolsets()

        if toolset_name not in available:
            return {
                "error": f"Unknown toolset: {toolset_name}",
                "available_toolsets": available,
                "instructions": "Choose from the available toolsets",
            }

        if _app is None:
            return {
                "error": "Tool inventory not initialized",
                "instructions": "Server not properly configured for runtime switching",
            }

        previous_toolset = _current_toolset

        if _current_toolset is not None:
            logger.info(f"Switching from '{_current_toolset}' to '{toolset_name}'")
            _disable_current_toolset_internal()

        tools_registered = _register_toolset_tools(toolset_name)
        _current_toolset = toolset_name

        try:
            await ctx.session.send_tool_list_changed()
            logger.info("Sent tools/list_changed notification to client")
        except Exception as notify_err:
            logger.warning(f"Could not send tools/list_changed notification: {notify_err}")

        metadata = load_toolset_metadata(toolset_name)

        return {
            "toolset_name": toolset_name,
            "status": "enabled",
            "description": metadata.get("description", "No description"),
            "tools_registered": tools_registered,
            "total_available_tools": tools_registered + 8,  # domain tools + 8 meta-tools
            "previous_toolset": previous_toolset,
            "message": f"Toolset '{toolset_name}' is now active with {tools_registered} domain tools. No restart required.",
        }
    except Exception as e:
        logger.error(f"Error in enable_toolset: {e}")
        return {"error": str(e), "status": "error"}


@log_tool_execution
async def disable_toolset(ctx: Context) -> Dict[str, Any]:
    """
    Disable the current toolset and return to meta-tools only mode.

    This removes all domain tools, leaving only the 6 meta-tools available.
    Use this to reduce context when switching tasks or when unsure which
    toolset is needed next.

    Returns:
        Dict containing:
        - status: "disabled" or "error"
        - disabled_toolset: The toolset that was disabled
        - tools_removed: Number of tools removed
        - remaining_tools: Number of tools still available (6 meta-tools)
    """
    global _current_toolset

    try:
        if _current_toolset is None:
            return {
                "status": "already_minimal",
                "message": "No toolset is currently active. Already in meta-tools only mode.",
                "remaining_tools": 8,
            }

        disabled_name = _current_toolset
        tools_removed = len(_registered_tool_names)

        _disable_current_toolset_internal()
        _current_toolset = None

        try:
            await ctx.session.send_tool_list_changed()
            logger.info("Sent tools/list_changed notification to client")
        except Exception as notify_err:
            logger.warning(f"Could not send tools/list_changed notification: {notify_err}")

        return {
            "status": "disabled",
            "disabled_toolset": disabled_name,
            "tools_removed": tools_removed,
            "remaining_tools": 8,
            "message": f"Toolset '{disabled_name}' disabled. Now in auto mode with 8 meta-tools.",
        }
    except Exception as e:
        logger.error(f"Error in disable_toolset: {e}")
        return {"error": str(e), "status": "error"}


def _register_toolset_tools(toolset_name: str) -> int:
    """Register tools for a toolset using dynamic generation. Returns tool count."""
    global _registered_tool_names

    if toolset_name not in _tool_inventory:
        logger.error(f"Toolset {toolset_name} not in inventory")
        return 0

    before_tools = set()
    if hasattr(_app, '_tool_manager') and _app._tool_manager:
        before_tools = set(_app._tool_manager._tools.keys())
    elif hasattr(_app, 'local_provider') and _app.local_provider:
        before_tools = set(_app.local_provider._tools.keys())

    register_toolset_tools(_app, toolset_name, _dct_client)

    after_tools = set()
    if hasattr(_app, '_tool_manager') and _app._tool_manager:
        after_tools = set(_app._tool_manager._tools.keys())
    elif hasattr(_app, 'local_provider') and _app.local_provider:
        after_tools = set(_app.local_provider._tools.keys())

    new_tools = after_tools - before_tools
    _registered_tool_names.extend(new_tools)

    logger.info(f"Toolset '{toolset_name}' enabled with {len(new_tools)} dynamically generated tools")
    return len(new_tools)


def _disable_current_toolset_internal():
    """Remove all currently registered domain tools."""
    global _registered_tool_names

    if not _registered_tool_names:
        return

    logger.info(f"Removing {len(_registered_tool_names)} domain tools...")

    for tool_name in _registered_tool_names:
        try:
            if hasattr(_app, '_tool_manager') and _app._tool_manager:
                if tool_name in _app._tool_manager._tools:
                    del _app._tool_manager._tools[tool_name]
                    logger.debug(f"Removed tool: {tool_name}")
            elif hasattr(_app, 'local_provider') and _app.local_provider:
                if hasattr(_app.local_provider, 'remove_tool'):
                    _app.local_provider.remove_tool(tool_name)
                    logger.debug(f"Removed tool: {tool_name}")
                elif tool_name in _app.local_provider._tools:
                    del _app.local_provider._tools[tool_name]
                    logger.debug(f"Removed tool: {tool_name}")
        except Exception as e:
            logger.warning(f"Could not remove tool {tool_name}: {e}")

    _registered_tool_names = []
    logger.info("Domain tools removed, now in meta-tools only mode")


@log_tool_execution
def check_operation_confirmation(method: str, api_path: str) -> Dict[str, Any]:
    """
    Check if an API operation requires manual confirmation.

    Use this tool before executing destructive operations to understand
    what level of confirmation is required.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        api_path: API endpoint path (e.g., "/vdbs/{vdbId}", "/bookmarks/{id}")

    Returns:
        Dict containing:
        - requires_confirmation: Whether confirmation is needed
        - level: Confirmation level (none, standard, elevated, manual)
        - message: Confirmation message to display
        - conditional: Whether confirmation is conditional
        - threshold_days: Days threshold for conditional confirmation
    """
    try:
        confirmation = get_confirmation_for_operation(method.upper(), api_path)

        return {
            "method": method.upper(),
            "api_path": api_path,
            "requires_confirmation": confirmation["level"] != "none",
            "level": confirmation["level"],
            "message": confirmation.get("message"),
            "conditional": confirmation.get("conditional", False),
            "threshold_days": confirmation.get("threshold_days"),
            "guidance": _get_confirmation_guidance(confirmation["level"]),
        }
    except Exception as e:
        logger.error(f"Error checking confirmation: {e}")
        return {"error": str(e)}


def _get_confirmation_guidance(level: str) -> str:
    """Get human-readable guidance for a confirmation level."""
    guidance = {
        "none": "No confirmation required. Proceed with the operation.",
        "standard": "Standard confirmation required. Verify the operation details before proceeding.",
        "elevated": "Elevated confirmation required. This operation has significant impact. Double-check all parameters.",
        "manual": "Manual confirmation required. This is a destructive operation. User must explicitly confirm.",
        "retention_check": "Check data retention policy before proceeding.",
        "policy_impact_check": "Check policy impact before proceeding.",
    }
    return guidance.get(level, "Unknown confirmation level")


@log_tool_execution
async def execute_action(
    toolset_name: str,
    tool_name: str,
    action: str,
    confirmed: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Execute any DCT API action directly — no enable_toolset or tool list refresh needed.

    Use this when domain tools are not yet visible in the tool list after enable_toolset,
    or as a direct one-shot execution path. Use list_available_toolsets and
    get_toolset_tools to discover the right toolset_name, tool_name, and action.

    Example flow:
      1. list_available_toolsets → see "continuous_data_admin"
      2. get_toolset_tools("continuous_data_admin") → see data_tool has action "list_dsources"
      3. execute_action(toolset_name="continuous_data_admin", tool_name="data_tool", action="list_dsources")

    For destructive operations, the first call returns confirmation_required.
    Re-call with confirmed=True after the user explicitly approves.

    Args:
        toolset_name: Toolset containing the tool (e.g., "continuous_data_admin")
        tool_name: Grouped tool name (e.g., "data_tool", "vdb_tool")
        action: Action to perform (e.g., "list_dsources", "search_vdbs")
        confirmed: Set True after user confirms a destructive operation
        **kwargs: Action-specific parameters (path params, query params, or body fields)

    Returns:
        API response dict, or confirmation_required dict for destructive operations
    """
    if _dct_client is None:
        return {"error": "DCT client not initialized"}

    try:
        available = get_available_toolsets()
        if toolset_name not in available:
            return {
                "error": f"Unknown toolset: {toolset_name}",
                "available_toolsets": available,
            }

        grouped_apis = load_toolset_grouped_apis(toolset_name)

        if tool_name not in grouped_apis:
            return {
                "error": f"Unknown tool '{tool_name}' in toolset '{toolset_name}'",
                "available_tools": list(grouped_apis.keys()),
            }

        apis = grouped_apis[tool_name].get("apis", [])
        api_info = next((a for a in apis if a["action"] == action), None)

        if api_info is None:
            return {
                "error": f"Unknown action '{action}' in tool '{tool_name}'",
                "available_actions": [a["action"] for a in apis],
            }

        method = api_info["method"]
        path = api_info["path"]

        # Confirmation check for destructive operations
        confirmation = get_confirmation_for_operation(method, path)
        if confirmation["level"] != "none" and not confirmed:
            return {
                "status": "confirmation_required",
                "confirmation_level": confirmation["level"],
                "confirmation_message": confirmation.get("message", "Please confirm this operation."),
                "action": action,
                "tool": tool_name,
                "toolset": toolset_name,
                "api_path": path,
                "instructions": (
                    "STOP: You MUST display the confirmation_message to the user and wait for their "
                    "EXPLICIT approval before re-calling with confirmed=True. Do NOT proceed without user consent."
                ),
            }

        # Substitute path parameters from kwargs
        final_path = path
        remaining = dict(kwargs)
        for match in re.finditer(r'\{(\w+)\}', path):
            param_name = match.group(1)
            if param_name in remaining:
                final_path = final_path.replace(f"{{{param_name}}}", str(remaining.pop(param_name)))

        # Handle filter_expression for search actions
        json_body = None
        filter_expr = remaining.pop("filter_expression", None)
        if filter_expr and "search" in action.lower():
            json_body = {"filter_expression": filter_expr}

        # Explicit body parameter takes precedence
        body = remaining.pop("body", None)
        if body:
            json_body = body

        # Non-None remaining kwargs: body for mutating methods, query params for GET/DELETE
        clean_remaining = {k: v for k, v in remaining.items() if v is not None}
        if method.upper() in ("POST", "PUT", "PATCH") and clean_remaining:
            if json_body:
                json_body.update(clean_remaining)
            else:
                json_body = clean_remaining
            query_params = {}
        else:
            query_params = clean_remaining

        return await _dct_client.make_request(
            method,
            final_path,
            params=query_params if query_params else None,
            json=json_body,
        )

    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Error in execute_action: {e}", exc_info=True)
        return {"error": str(e)}


@log_tool_execution
def find_endpoint(
    query: str,
    method_types: Optional[List[str]] = None,
    limit: int = 10,
    min_score: float = 0.15,
) -> Dict[str, Any]:
    """
    Find the best-matching DCT API endpoint(s) for a free-text user intent
    by fuzzy-matching against the cached OpenAPI spec.

    The OpenAPI spec is the source of truth. Each candidate result includes
    method, path, operation_id, summary, tags, score, confirmation level,
    and a `suggested_toolset` hint pointing to the persona that exposes the
    endpoint (if any) — call enable_toolset() with that name, or use
    execute_action() directly if you already have the path.

    Use `get_spec_chunk(ref)` afterwards to resolve any $ref pointers
    (parameters, schemas, requestBodies) on demand.

    Args:
        query: Free-text user intent (e.g. "list all compliance connectors")
        method_types: Optional HTTP method filter, e.g. ["GET"], ["POST"].
            When ["GET"] is given, POST /*/search endpoints are also included
            (semantically read-equivalent).
        limit: Max candidates to return (default 10, hard cap 25).
        min_score: Drop candidates below this score (default 0.15).

    Returns:
        {"candidates": [...], "source": "openapi_spec", ...} on success, or
        {"error": "...", "candidates": []} on failure.
    """
    if not query or not query.strip():
        return {
            "error": "query is required",
            "hint": "Provide a free-text user intent, e.g. 'list all compliance connectors'",
            "candidates": [],
        }

    spec = get_cached_spec()
    if spec is None:
        return {
            "error": "OpenAPI spec not available; cannot perform fuzzy discovery.",
            "hint": "Spec is cached at startup; ensure DCT_BASE_URL is reachable.",
            "candidates": [],
        }

    capped_limit = max(1, min(int(limit) if limit else 10, HARD_LIMIT))

    try:
        corpus = build_corpus_from_spec(spec)
        hot = extract_hot_keywords_from_spec(spec)
        ranked = rank_candidates(
            corpus, query, method_types, float(min_score), capped_limit, hot
        )
    except Exception as e:
        logger.error(f"find_endpoint ranking failed: {e}", exc_info=True)
        return {"error": str(e), "candidates": []}

    available_toolsets = get_available_toolsets()
    enriched: List[Dict[str, Any]] = []
    for cand in ranked:
        method, path = cand["method"], cand["path"]
        try:
            confirmation = get_confirmation_for_operation(method, path)
            level = confirmation.get("level", "none")
        except Exception as ce:
            logger.warning(f"confirmation lookup failed for {method} {path}: {ce}")
            level = "none"

        suggested_toolset = None
        for ts in available_toolsets:
            try:
                grouped = load_toolset_grouped_apis(ts)
            except Exception:
                continue
            for tool_info in grouped.values():
                for api in tool_info.get("apis", []):
                    if api.get("method") == method and api.get("path") == path:
                        suggested_toolset = ts
                        break
                if suggested_toolset:
                    break
            if suggested_toolset:
                break

        enriched.append({
            "score": cand["score"],
            "method": method,
            "path": path,
            "operation_id": cand.get("operation_id", ""),
            "summary": cand.get("summary", ""),
            "tags": cand.get("tags", []),
            "requires_confirmation": level != "none",
            "confirmation_level": level,
            "suggested_toolset": suggested_toolset,
        })

    logger.info(
        f"find_endpoint query='{query}' method_types={method_types} "
        f"returned={len(enriched)} source=openapi_spec"
    )

    if not enriched:
        return {
            "candidates": [],
            "source": "openapi_spec",
            "hint": (
                "No fuzzy match. Try list_available_toolsets to browse personas, "
                "or refine the query."
            ),
        }

    return {
        "candidates": enriched,
        "source": "openapi_spec",
        "count": len(enriched),
        "instructions": (
            "Inspect candidates and pick the best match. If suggested_toolset "
            "is set, call enable_toolset(name) then use the domain tool, or "
            "call execute_action(toolset_name=suggested_toolset, ...) directly. "
            "Use get_spec_chunk(ref) to resolve $ref pointers from the spec."
        ),
    }


@log_tool_execution
def get_spec_chunk(ref: str) -> Dict[str, Any]:
    """
    Resolve a JSON-pointer / OpenAPI $ref against the cached spec.

    Use this after find_endpoint to fetch parameter, schema, or requestBody
    definitions on demand — e.g. resolving "#/components/parameters/limit"
    referenced by /dsources/search.

    Args:
        ref: JSON pointer string. Accepts the leading "#/" form (standard
             OpenAPI $ref) or a plain "/components/parameters/limit" form.

    Returns:
        {"ref": "...", "value": <resolved object>} on success, or
        {"error": "...", "ref": "..."} on failure.
    """
    if not ref or not isinstance(ref, str):
        return {"error": "ref is required (string)", "ref": ref}

    spec = get_cached_spec()
    if spec is None:
        return {"error": "OpenAPI spec not available", "ref": ref}

    pointer = ref.lstrip("#")
    if not pointer.startswith("/"):
        return {
            "error": (
                "ref must be a JSON pointer like '#/components/parameters/limit' "
                "or '/components/parameters/limit'"
            ),
            "ref": ref,
        }

    parts = [
        p.replace("~1", "/").replace("~0", "~")
        for p in pointer.split("/")[1:]
        if p != ""
    ]

    node: Any = spec
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return {"error": f"ref segment '{part}' not resolvable", "ref": ref}
        else:
            return {"error": f"ref segment '{part}' not found in spec", "ref": ref}

    return {"ref": ref, "value": node}


def register_meta_tools(app):
    """
    Register the 8 meta-tools for auto mode.

    Args:
        app: FastMCP application instance
    """
    logger.info("Registering 8 meta-tools for auto mode...")

    try:
        app.add_tool(list_available_toolsets, name="list_available_toolsets")
        logger.info("  Registered: list_available_toolsets")

        app.add_tool(get_toolset_tools, name="get_toolset_tools")
        logger.info("  Registered: get_toolset_tools")

        app.add_tool(enable_toolset, name="enable_toolset")
        logger.info("  Registered: enable_toolset")

        app.add_tool(disable_toolset, name="disable_toolset")
        logger.info("  Registered: disable_toolset")

        app.add_tool(check_operation_confirmation, name="check_operation_confirmation")
        logger.info("  Registered: check_operation_confirmation")

        app.add_tool(execute_action, name="execute_action")
        logger.info("  Registered: execute_action")

        app.add_tool(find_endpoint, name="find_endpoint")
        logger.info("  Registered: find_endpoint")

        app.add_tool(get_spec_chunk, name="get_spec_chunk")
        logger.info("  Registered: get_spec_chunk")

        logger.info("Meta-tools registration completed (8 tools).")
    except Exception as e:
        logger.error(f"Error registering meta-tools: {e}")
        raise


def get_current_toolset() -> Optional[str]:
    """Return the currently active toolset name, or None if in meta-tools only mode."""
    return _current_toolset


def get_registered_tool_count() -> int:
    """Return the number of currently registered domain tools."""
    return len(_registered_tool_names)
