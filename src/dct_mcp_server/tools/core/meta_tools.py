"""
Spec discovery helpers for the DCT MCP Server.

These were originally the auto-mode meta-tools. Auto mode has been removed
(DLPXECO-14257); the two reusable, spec-reading helpers below are retained as
standalone utilities — they are NOT registered as MCP tools — so they remain
available to wire into dynamic mode later:

- find_endpoint:  Fuzzy-match a free-text intent against the cached OpenAPI spec.
- get_spec_chunk: Resolve a $ref / JSON-pointer against the cached OpenAPI spec.

Both read the OpenAPI spec from the spec cache (tool_factory.get_cached_spec).
"""

import logging
from functools import lru_cache
from typing import Dict, Any, List, Optional, Tuple

from dct_mcp_server.config import (
    get_available_toolsets,
    load_toolset_grouped_apis,
)
from dct_mcp_server.core.decorators import log_tool_execution
from .dynamic_confirmation import resolve_confirmation
from .tool_factory import get_cached_spec
from .endpoint_discovery import (
    get_discovery_index,
    rank_candidates,
)

HARD_LIMIT = 25

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _endpoint_toolset_index() -> Dict[Tuple[str, str], str]:
    """Reverse index mapping (method, path) -> first toolset that exposes it.

    Built once from all toolset configs. Iterating toolsets in the order
    get_available_toolsets() returns and keeping the first writer preserves the
    original first-match-wins behaviour of find_endpoint's nested scan, while
    turning the per-candidate lookup into an O(1) dict access. Cached for the
    process lifetime — toolset configs do not change during a session.
    """
    index: Dict[Tuple[str, str], str] = {}
    for ts in get_available_toolsets():
        try:
            grouped = load_toolset_grouped_apis(ts)
        except Exception:
            continue
        for tool_info in grouped.values():
            for api in tool_info.get("apis", []):
                key = (api.get("method"), api.get("path"))
                index.setdefault(key, ts)
    return index


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
    endpoint (if any) — run the server with DCT_TOOLSET set to that persona
    to expose its tools.

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

    try:
        capped_limit = max(1, min(int(limit) if limit else 10, HARD_LIMIT))
    except (TypeError, ValueError):
        return {
            "error": f"limit must be an integer, got {limit!r}",
            "candidates": [],
        }

    try:
        index = get_discovery_index(spec)
        ranked = rank_candidates(
            index["corpus"],
            query,
            method_types,
            float(min_score),
            capped_limit,
            index["hot_keywords"],
        )
    except Exception as e:
        logger.error(f"find_endpoint ranking failed: {e}", exc_info=True)
        return {"error": str(e), "candidates": []}

    toolset_index = _endpoint_toolset_index()
    enriched: List[Dict[str, Any]] = []
    for cand in ranked:
        method, path = cand["method"], cand["path"]
        try:
            confirmation = resolve_confirmation(method, path)
            level = confirmation.get("level", "none")
        except Exception as ce:
            logger.warning(f"confirmation lookup failed for {method} {path}: {ce}")
            level = "none"

        suggested_toolset = toolset_index.get((method, path))

        enriched.append(
            {
                "score": cand["score"],
                "method": method,
                "path": path,
                "operation_id": cand.get("operation_id", ""),
                "summary": cand.get("summary", ""),
                "tags": cand.get("tags", []),
                "requires_confirmation": level != "none",
                "confirmation_level": level,
                "suggested_toolset": suggested_toolset,
            }
        )

    logger.info(
        f"find_endpoint query='{query}' method_types={method_types} "
        f"returned={len(enriched)} source=openapi_spec"
    )

    if not enriched:
        return {
            "candidates": [],
            "source": "openapi_spec",
            "hint": (
                "No fuzzy match. Try a broader query, or run the server with "
                "DCT_TOOLSET set to a persona to browse its tools."
            ),
        }

    return {
        "candidates": enriched,
        "source": "openapi_spec",
        "count": len(enriched),
        "instructions": (
            "Inspect candidates and pick the best match. If suggested_toolset "
            "is set, run the server with DCT_TOOLSET set to that persona to "
            "expose its tools. Use get_spec_chunk(ref) to resolve $ref pointers "
            "from the spec."
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
