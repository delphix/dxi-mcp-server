"""
Executions tools (Continuous Compliance)

Provides read-only access to job executions.
"""

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from ...client import DCTAPIClient

logger = logging.getLogger(__name__)


def register_executions_tools(mcp: FastMCP, client: DCTAPIClient):
    @mcp.tool()
    async def list_executions(
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        sort: Optional[str] = None,
        job_id: Optional[str] = None,
        path_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List executions.

        By default hits 'executions'. Provide job_id to filter if supported.
        Use path_override to specify an exact API path if your DCT differs.
        """
        params = {}
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        if sort is not None:
            params["sort"] = sort
        if job_id is not None:
            params["job_id"] = job_id
        path = path_override or "executions"
        return await client.make_request("GET", path, params=params)

    @mcp.tool()
    async def get_execution(execution_id: str, path_override: Optional[str] = None) -> Dict[str, Any]:
        """Get an execution by ID.

        Default path is 'executions/{id}'. Use path_override to customize.
        """
        path = path_override or f"executions/{execution_id}"
        return await client.make_request("GET", path)

    @mcp.tool()
    async def list_execution_components(execution_id: str, path_override: Optional[str] = None) -> Dict[str, Any]:
        """List components processed in an execution.

        Tries common endpoint patterns:
        - executions/{id}/components (default)
        - job-executions/{id}/components
        - executions/{id}/details
        You may provide path_override to use the exact path for your DCT.
        """
        candidates = [
            path_override or f"executions/{execution_id}/components",
            f"job-executions/{execution_id}/components",
            f"executions/{execution_id}/details",
        ]
        last_error: Optional[Dict[str, Any]] = None
        for p in candidates:
            try:
                return await client.make_request("GET", p)
            except Exception as e:
                last_error = {"error": str(e), "path": p}
                continue
        return {
            "error": "not_found",
            "message": "No execution components endpoint found for this execution on current DCT release.",
            "execution_id": execution_id,
            "tried_paths": candidates,
            "last_error": last_error,
            "suggestions": [
                "Use path_override to specify the exact components endpoint.",
                "Review execution details payload; components may be embedded.",
            ],
        }

    @mcp.tool()
    async def get_execution_component(
        execution_id: str,
        component_id: str,
        path_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a specific component from an execution.

        Tries common endpoint patterns:
        - executions/{execution_id}/components/{component_id}
        - job-executions/{execution_id}/components/{component_id}
        - executions/{execution_id}/details (filter client-side if components embedded)
        Provide path_override to specify the exact API path.
        """
        candidates = [
            path_override or f"executions/{execution_id}/components/{component_id}",
            f"job-executions/{execution_id}/components/{component_id}",
        ]
        last_error: Optional[Dict[str, Any]] = None
        for p in candidates:
            try:
                return await client.make_request("GET", p)
            except Exception as e:
                last_error = {"error": str(e), "path": p}
                continue

        # Fallback: fetch details and try to locate component client-side
        try:
            details = await client.make_request("GET", f"executions/{execution_id}/details")
            comps = details.get("components") or details.get("items") or []
            for c in comps:
                if isinstance(c, dict) and str(c.get("id")) == str(component_id):
                    return c
            return {
                "error": "component_not_found",
                "message": "Component not found in execution details payload.",
                "execution_id": execution_id,
                "component_id": component_id,
                "checked_keys": ["components", "items"],
            }
        except Exception as e:
            return {
                "error": "not_found",
                "message": "No execution component endpoint found for this execution on current DCT release.",
                "execution_id": execution_id,
                "component_id": component_id,
                "last_error": last_error or {"error": str(e)},
                "suggestions": [
                    "Use path_override to specify the exact component endpoint.",
                    "Inspect execution details in DCT UI to confirm component IDs.",
                ],
            }

    logger.info("Executions tools registered successfully (continuous_compliance)")
