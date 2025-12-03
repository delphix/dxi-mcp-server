"""
Connector tools (Continuous Compliance)
"""

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from ...client import DCTAPIClient

logger = logging.getLogger(__name__)


def register_connector_tools(mcp: FastMCP, client: DCTAPIClient):
    @mcp.tool()
    async def list_connectors(limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        if sort is not None:
            params["sort"] = sort
        return await client.make_request("GET", "connectors", params=params)

    @mcp.tool()
    async def search_connectors(
        search_criteria: Dict[str, Any],
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        params = {}
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        if sort is not None:
            params["sort"] = sort
        return await client.make_request("POST", "connectors/search", data={"filter_expression": search_criteria}, params=params)

    @mcp.tool()
    async def get_connector(connector_id: str) -> Dict[str, Any]:
        return await client.make_request("GET", f"connectors/{connector_id}")

    @mcp.tool()
    async def create_connector(*args, **kwargs) -> Dict[str, Any]:
        return {
            "error": "incomplete_implementation",
            "message": "Connector creation requires additional required fields that need to be identified.",
            "details": "Missing required fields: 'type', 'job_orchestrator_id'. Full field requirements need documentation.",
            "status": "implementation_pending",
        }

    @mcp.tool()
    async def update_connector(connector_id: str, *args, **kwargs) -> Dict[str, Any]:
        return {
            "error": "read_only",
            "message": "Connector updates are not currently supported - connectors are read-only.",
            "details": "The connector object is read only and cannot be modified.",
            "connector_id": connector_id,
            "status": "feature_unavailable",
        }

    logger.info("Connector tools registered successfully (continuous_compliance)")
