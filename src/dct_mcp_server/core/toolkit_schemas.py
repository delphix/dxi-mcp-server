"""
Toolkit schema prefetching and MCP resource registration.

At server startup, fetches all toolkit definitions from the DCT instance
via POST /toolkits/search and caches them as individual JSON files under
$TEMP/dct_toolkit_schemas/.  Each cached toolkit is also registered as an
MCP resource so the AI client can discover and read schema definitions
(virtual_source_definition, linked_source_definition, etc.) without an
extra API round-trip during link or provision operations.
"""

import json
import os
import tempfile
from typing import Any, Dict, List, Optional

from dct_mcp_server.core.logging import get_logger

logger = get_logger(__name__)

TOOLKIT_SCHEMAS_DIR = os.path.join(tempfile.gettempdir(), "dct_toolkit_schemas")


# ---------------------------------------------------------------------------
# Fetch & cache
# ---------------------------------------------------------------------------

async def fetch_and_cache_toolkit_schemas(dct_client) -> tuple[list[dict], dict[str, str]]:
    """
    Fetch all toolkits from the DCT instance and persist each one as a
    JSON file under *TOOLKIT_SCHEMAS_DIR*.

    Returns a tuple of:
    - list of toolkit dicts that were cached
    - dict mapping display_name -> toolkit_id for resource registration
    """
    os.makedirs(TOOLKIT_SCHEMAS_DIR, exist_ok=True)

    all_toolkits: list[dict] = []
    seen_ids: set[str] = set()
    display_name_to_id: dict[str, str] = {}
    cursor = None

    while True:
        params: dict = {"limit": 50}
        if cursor:
            params["cursor"] = cursor

        response = await dct_client.make_request(
            "POST", "/toolkits/search", params=params, json={}
        )

        items = response.get("items", [])
        if not items:
            break

        for toolkit in items:
            toolkit_id = toolkit.get("id")
            if not toolkit_id:
                continue
            file_path = os.path.join(TOOLKIT_SCHEMAS_DIR, f"{toolkit_id}.json")
            with open(file_path, "w") as f:
                json.dump(toolkit, f, indent=2)
            all_toolkits.append(toolkit)
            seen_ids.add(toolkit_id)

            display_name = (
                toolkit.get("display_name")
                or toolkit.get("pretty_name")
                or toolkit.get("name")
                or toolkit_id
            )
            display_name_to_id[display_name] = toolkit_id
            logger.debug(f"Cached toolkit schema: {toolkit_id} (display_name={display_name})")

        response_metadata = response.get("response_metadata", {})
        cursor = response_metadata.get("next_cursor")
        if not cursor:
            break

    # Remove stale files for toolkits no longer in DCT
    if os.path.isdir(TOOLKIT_SCHEMAS_DIR):
        for fn in os.listdir(TOOLKIT_SCHEMAS_DIR):
            if fn.endswith(".json"):
                stale_id = fn.removesuffix(".json")
                if stale_id not in seen_ids:
                    os.remove(os.path.join(TOOLKIT_SCHEMAS_DIR, fn))
                    logger.debug(f"Removed stale toolkit cache: {stale_id}")

    logger.info(
        f"Cached {len(all_toolkits)} toolkit schema(s) in {TOOLKIT_SCHEMAS_DIR}"
    )
    return all_toolkits, display_name_to_id


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def get_cached_toolkit_schema(toolkit_id: str) -> Optional[Dict[str, Any]]:
    """Return a previously cached toolkit dict by ID, or None."""
    file_path = os.path.join(TOOLKIT_SCHEMAS_DIR, f"{toolkit_id}.json")
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r") as f:
        return json.load(f)


def list_cached_toolkit_ids() -> List[str]:
    """Return the IDs of all cached toolkit schemas."""
    if not os.path.isdir(TOOLKIT_SCHEMAS_DIR):
        return []
    return [
        fn.removesuffix(".json")
        for fn in os.listdir(TOOLKIT_SCHEMAS_DIR)
        if fn.endswith(".json")
    ]


# ---------------------------------------------------------------------------
# MCP resource registration
# ---------------------------------------------------------------------------

def register_toolkit_resources(
    app,
    toolkits: list[dict],
    display_name_to_id: dict[str, str],
) -> int:
    """
    Register each toolkit as an MCP resource on *app*.

    Registers:
    1. A template resource ``toolkit://{toolkit_id}/schema`` — handles any
       toolkit_id returned by get_vdb / get_dsource API responses.
    2. A concrete resource ``toolkit://{display_name}/schema`` per toolkit —
       discoverable via list_resources; AI can infer display_name from the
       user prompt (e.g. "mysql-plugin" from "create a MySQL dSource").

    Returns the number of concrete resources registered.
    """
    import urllib.parse
    from mcp.server.fastmcp.resources import FunctionResource
    from pydantic import AnyUrl

    # -- template resource: resolves any toolkit_id (including cache misses) --
    @app.resource(
        "toolkit://{toolkit_id}/schema",
        name="toolkit_schema",
        title="Toolkit Schema Definition",
        description=(
            "Schema definitions for a DCT toolkit/connector. Contains "
            "virtual_source_definition, linked_source_definition, "
            "discovery_definition, snapshot_parameters_definition and more. "
            "Use this when you already have a toolkit_id from a VDB or dSource object."
        ),
        mime_type="application/json",
    )
    def _toolkit_schema_template(toolkit_id: str) -> str:
        schema = get_cached_toolkit_schema(toolkit_id)
        if schema is None:
            return json.dumps({"error": f"Toolkit '{toolkit_id}' not found in cache."})
        return json.dumps(schema, indent=2)

    # -- concrete resources keyed by display_name for prompt-driven discovery --
    registered = 0
    for display_name, toolkit_id in display_name_to_id.items():
        safe_name = urllib.parse.quote(display_name, safe="-_.")

        def _make_reader(tid: str):
            def _read() -> str:
                schema = get_cached_toolkit_schema(tid)
                if schema is None:
                    return json.dumps({"error": f"Toolkit '{tid}' not found in cache."})
                return json.dumps(schema, indent=2)
            return _read

        resource = FunctionResource(
            uri=AnyUrl(f"toolkit://{safe_name}/schema"),
            name=f"toolkit_schema_{safe_name}",
            title=f"Toolkit: {display_name}",
            description=(
                f"Schema for toolkit '{display_name}'. Contains "
                f"virtual_source_definition, linked_source_definition, "
                f"discovery_definition, snapshot_parameters_definition, etc. "
                f"Read this before AppData link or provision operations when "
                f"the plugin type is known from context."
            ),
            mime_type="application/json",
            fn=_make_reader(toolkit_id),
        )
        app.add_resource(resource)
        registered += 1
        logger.debug(f"Registered MCP resource: toolkit://{safe_name}/schema -> {toolkit_id}")

    logger.info(f"Registered {registered} toolkit schema MCP resource(s) by display_name")
    return registered
