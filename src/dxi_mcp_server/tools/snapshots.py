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
        limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None
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
        filter_expression: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search for snapshots with filter expressions

        Args:
            filter_expression: Filter expression string (e.g., "dataset_id EQ 'ds-123' AND timestamp GE 2024-01-01T00:00:00.000Z")
            limit: Maximum number of results to return
            cursor: Pagination cursor
            sort: Sort order

        Available filterable fields:
            - id
            - engine_id
            - namespace
            - name
            - namespace_id
            - namespace_name
            - is_replica
            - consistency
            - missing_non_logged_data
            - dataset_id
            - creation_time
            - start_timestamp
            - start_location
            - timestamp
            - location
            - expiration
            - retain_forever
            - effective_expiration
            - effective_retain_forever
            - timeflow_id
            - timezone
            - version
            - temporary
            - appdata_toolkit
            - appdata_metadata

        Literal values (per API docs):
            - Nil: nil (case-insensitive)
            - Boolean: true, false (unquoted)
            - Number: 0, 1, -1, 1.2, 1.2e-2 (unquoted)
            - String: quoted, e.g., 'foo', "bar"
            - Datetime: RFC3339 literal without quotes, e.g., 2018-04-27T18:39:26.397237+00:00
            - List: [0], [0, 1], ['foo', "bar"]

        Important:
            - Quote strings; do NOT quote datetimes.
            - Example: creation_time GE 2024-01-01T00:00:00.000Z

        Returns:
            Dictionary containing search results and pagination metadata
        """
        try:
            params = {}
            if limit is not None:
                params["limit"] = limit
            if cursor:
                params["cursor"] = cursor
            if sort:
                params["sort"] = sort

            # Prepare search body
            search_body = {"filter_expression": filter_expression}

            result = await client.make_request(
                "POST",
                "snapshots/search",
                params=params,
                json=search_body,
            )
            logger.info(
                f"Found {len(result.get('items', []))} snapshots matching filter expression"
            )
            return result

        except Exception as e:
            logger.error(f"Error searching snapshots: {str(e)}")
            raise

    @mcp.tool()
    async def get_snapshot(snapshot_id: str) -> Dict[str, Any]:
        """Get snapshot details

        Args:
            snapshot_id: Snapshot ID
        """
        return await client.make_request("GET", f"snapshots/{snapshot_id}")

    @mcp.tool()
    async def delete_snapshot(snapshot_id: str, delete_all_dependencies: Optional[bool] = None) -> Dict[str, Any]:
        """Delete a snapshot

        Args:
            snapshot_id: Snapshot ID
        """
        body: Dict[str, Any] = {}
        if delete_all_dependencies is not None:
            body["delete_all_dependencies"] = delete_all_dependencies
        return await client.make_request("POST", f"snapshots/{snapshot_id}/delete", json=body)

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
