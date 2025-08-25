"""
Bookmark tools for DCT API
"""

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from ..client import DCTAPIClient

logger = logging.getLogger(__name__)


def register_bookmark_tools(mcp: FastMCP, client: DCTAPIClient):
    """Register Bookmark-related tools"""

        @app.tool()
    async def list_bookmarks(
        limit: Optional[int] = None, cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all bookmarks

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
            "GET", "bookmarks", params=params
        )

        @app.tool()
    async def search_bookmarks(
        search_criteria: Dict[str, Any],
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search for bookmarks with filters

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
            "bookmarks/search",
            data={"filter": filter},
            params=params,
        )

        @app.tool()
    async def get_bookmark(bookmark_id: str) -> Dict[str, Any]:
        """Get bookmark details

        Args:
            bookmark_id: Bookmark ID
        """
        return await client.make_request("GET", f"bookmarks/{bookmark_id}")

    @app.tool()
    async def create_bookmark(
        name: str,
        dataset_id: str = None,
        vdb_ids: list = None,
        tags: list = None,
        retention_policy: str = None,
    ) -> Dict[str, Any]:
        """Create a bookmark at the current time

        Args:
            name: Bookmark name
            dataset_id: Dataset ID (optional, for dSource bookmarks)
            vdb_ids: List of VDB IDs (optional, for VDB Group bookmarks)
            tags: List of tags
            retention_policy: Retention policy
        """
        data = {"name": name}
        
        if dataset_id:
            data["datasetId"] = dataset_id
        if vdb_ids:
            data["vdbIds"] = vdb_ids
        if tags:
            data["tags"] = tags
        if retention_policy:
            data["retentionPolicy"] = retention_policy

        return await client.make_request("POST", "bookmarks", data=data)

        @app.tool()
    async def delete_bookmark(bookmark_id: str) -> Dict[str, Any]:
        """Delete a bookmark

        Args:
            bookmark_id: Bookmark ID
        """
        return await client.make_request("DELETE", f"bookmarks/{bookmark_id}")

        @app.tool()
    async def update_bookmark(
        bookmark_id: str,
        name: str = None,
        tags: list = None,
        retention_policy: str = None,
    ) -> Dict[str, Any]:
        """Update a bookmark

        Args:
            bookmark_id: Bookmark ID
            name: New bookmark name (optional)
            tags: New list of tags (optional)
            retention_policy: New retention policy (optional)
        """
        data = {}
        if name:
            data["name"] = name
        if tags:
            data["tags"] = tags
        if retention_policy:
            data["retentionPolicy"] = retention_policy

        return await client.make_request("PATCH", f"bookmarks/{bookmark_id}", data=data)

    logger.info("Bookmark tools registered successfully")
