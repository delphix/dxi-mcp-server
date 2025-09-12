"""
Bookmark tools for DCT API
"""

import logging
from typing import Any, Dict, Optional, List

from mcp.server.fastmcp import FastMCP

from ..client import DCTAPIClient

logger = logging.getLogger(__name__)


def register_bookmark_tools(mcp: FastMCP, client: DCTAPIClient):
    """Register Bookmark-related tools"""

    @mcp.tool()
    async def list_bookmarks(
        limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None
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

    @mcp.tool()
    async def search_bookmarks(
        filter_expression: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search for bookmarks with filter expressions

        Args:
            filter_expression: Filter expression string (e.g., "name CONTAINS 'backup' AND tags CONTAINS 'production'")
            limit: Maximum number of results to return
            cursor: Pagination cursor
            sort: Sort order

        Available filterable fields:
            - id
            - name
            - creation_date
            - data_timestamp
            - vdb_ids
            - dsource_ids
            - retention
            - expiration
            - bookmark_source
            - bookmark_status
            - ss_data_layout_id
            - ss_bookmark_reference

        Literal values (per API docs):
            - Nil: nil (case-insensitive)
            - Boolean: true, false (unquoted)
            - Number: 0, 1, -1, 1.2, 1.2e-2 (unquoted)
            - String: quoted, e.g., 'foo', "bar"
            - Datetime: RFC3339 literal without quotes, e.g., 2018-04-27T18:39:26.397237+00:00
            - List: [0], [0, 1], ['foo', "bar"]

        Important:
            - Quote strings; do NOT quote datetimes.
            - Example: data_timestamp GE 2024-01-01T00:00:00.000Z

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
                "bookmarks/search",
                params=params,
                json=search_body,
            )
            logger.info(
                f"Found {len(result.get('items', []))} bookmarks matching filter expression"
            )
            return result

        except Exception as e:
            logger.error(f"Error searching bookmarks: {str(e)}")
            raise

    @mcp.tool()
    async def get_bookmark(bookmark_id: str) -> Dict[str, Any]:
        """Get bookmark details

        Args:
            bookmark_id: Bookmark ID
        """
        return await client.make_request("GET", f"bookmarks/{bookmark_id}")

    @mcp.tool()
    async def create_bookmark(
        name: str,
        vdb_ids: Optional[List[str]] = None,
        vdb_group_id: Optional[str] = None,
        snapshot_ids: Optional[List[str]] = None,
        timeflow_ids: Optional[List[str]] = None,
        timestamp: Optional[str] = None,
        timestamp_in_database_timezone: Optional[str] = None,
        location: Optional[str] = None,
        retention: Optional[int] = None,
        expiration: Optional[str] = None,
        retain_forever: Optional[bool] = None,
        tags: Optional[List[Dict[str, str]]] = None,
        bookmark_type: Optional[str] = None,
        make_current_account_owner: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Create a bookmark at the current time

        Args:
            name: Bookmark name
            vdb_ids: IDs of VDBs to include (mutually exclusive with vdb_group_id)
            vdb_group_id: VDB group ID (mutually exclusive with vdb_ids)
            snapshot_ids: IDs of snapshots to include
            timeflow_ids: IDs of timeflows (used with timestamp/timestamp_in_database_timezone/location)
            timestamp: Point-in-time (ISO 8601)
            timestamp_in_database_timezone: Point-in-time in database timezone
            location: SCN/LSN location
            retention: Deprecated retention days (-1 for forever)
            expiration: Expiration date
            retain_forever: Retain bookmark forever
            tags: List of {key, value}
            bookmark_type: PUBLIC or PRIVATE
            make_current_account_owner: Set current account as owner
        """
        body: Dict[str, Any] = {"name": name}

        if vdb_ids is not None:
            body["vdb_ids"] = vdb_ids
        if vdb_group_id is not None:
            body["vdb_group_id"] = vdb_group_id
        if snapshot_ids is not None:
            body["snapshot_ids"] = snapshot_ids
        if timeflow_ids is not None:
            body["timeflow_ids"] = timeflow_ids
        if timestamp is not None:
            body["timestamp"] = timestamp
        if timestamp_in_database_timezone is not None:
            body["timestamp_in_database_timezone"] = timestamp_in_database_timezone
        if location is not None:
            body["location"] = location
        if retention is not None:
            body["retention"] = retention
        if expiration is not None:
            body["expiration"] = expiration
        if retain_forever is not None:
            body["retain_forever"] = retain_forever
        if tags is not None:
            body["tags"] = tags
        if bookmark_type is not None:
            body["bookmark_type"] = bookmark_type
        if make_current_account_owner is not None:
            body["make_current_account_owner"] = make_current_account_owner

        return await client.make_request("POST", "bookmarks", json=body)

    @mcp.tool()
    async def delete_bookmark(bookmark_id: str) -> Dict[str, Any]:
        """Delete a bookmark

        Args:
            bookmark_id: Bookmark ID
        """
        return await client.make_request("DELETE", f"bookmarks/{bookmark_id}")

    # Update bookmark is not supported by the API; omitting tool.

    logger.info("Bookmark tools registered successfully")
