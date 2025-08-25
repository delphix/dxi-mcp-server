"""
Snapshot tools for DCT API
"""

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from ..client import DCTAPIClient

logger = logging.getLogger(__name__)


def register_snapshot_tools(mcp: FastMCP, client: DCTAPIClient):
    """Register Snapshot-related tools"""

    @mcp.tool()
    async def list_snapshots(
        limit: Optional[int] = None, cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all snapshots

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
            "GET", "snapshots", params=params
        )

    @mcp.tool()
    async def search_snapshots(
        search_criteria: Dict[str, Any],
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search for snapshots with filters

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
            "snapshots/search",
            data={"filter": filter},
            params=params,
        )

    @mcp.tool()
    async def get_snapshot(snapshot_id: str) -> Dict[str, Any]:
        """Get snapshot details

        Args:
            snapshot_id: Snapshot ID
        """
        return await client.make_request("GET", f"snapshots/{snapshot_id}")

    @mcp.tool()
    async def delete_snapshot(snapshot_id: str) -> Dict[str, Any]:
        """Delete a snapshot

        Args:
            snapshot_id: Snapshot ID
        """
        return await client.make_request("POST", f"snapshots/{snapshot_id}/delete")

    @mcp.tool()
    async def dct_snapshots_find_by_timestamp(
        dataset_id: str,
        timestamp: str,
    ) -> Dict[str, Any]:
        """Find snapshots by timestamp

        Args:
            dataset_id: Dataset ID (dSource or VDB)
            timestamp: Timestamp to search for (ISO format)
        """
        params = {
            "dataset_id": dataset_id,
            "timestamp": timestamp,
        }
        return await client.make_request("GET", "snapshots/find_by_timestamp", params=params)

    @mcp.tool()
    async def dct_snapshots_find_by_location(
        dataset_id: str,
        location: str,
    ) -> Dict[str, Any]:
        """Find snapshots by location/SCN

        Args:
            dataset_id: Dataset ID (dSource or VDB)
            location: Location/SCN to search for
        """
        params = {
            "dataset_id": dataset_id,
            "location": location,
        }
        return await client.make_request("GET", "snapshots/find_by_location", params=params)

    logger.info("Snapshot tools registered successfully")
