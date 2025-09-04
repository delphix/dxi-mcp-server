"""
Engine tools for DCT API
"""

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from ..client import DCTAPIClient

logger = logging.getLogger(__name__)


def register_engine_tools(mcp: FastMCP, client: DCTAPIClient):
    """Register Engine-related tools"""

    @mcp.tool()
    async def list_engines(
        limit: Optional[int] = None, cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all engines

        Args:
            limit: Maximum number of results to return
            cursor: Pagination cursor
            sort: Sort order
        """
        params = {}
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        if sort is not None:
            params["sort"] = sort

        return await client.make_request(
            "GET", "management/engines", params=params
        )

    @mcp.tool()
    async def search_engines(
        search_criteria: Dict[str, Any],
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search for engines with filters

        Args:
            limit: Maximum number of results to return
            cursor: Pagination cursor
            sort: Sort order
            filter: Search filters
        """
        params = {}
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        if sort is not None:
            params["sort"] = sort

        return await client.make_request(
            "POST",
            "management/engines/search",
            data={"filter": filter},
            params=params,
        )

    @mcp.tool()
    async def get_engine(engine_id: str) -> Dict[str, Any]:
        """Get engine details

        Args:
            engine_id: Engine ID
        """
        return await client.make_request("GET", f"management/engines/{engine_id}")

    logger.info("Engine tools registered successfully")
