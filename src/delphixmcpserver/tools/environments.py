"""
Environment tools for DCT API
"""

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from ..client import DCTAPIClient

logger = logging.getLogger(__name__)


def register_environment_tools(mcp: FastMCP, client: DCTAPIClient):
    """Register Environment-related tools"""

    @mcp.tool()
    async def dct_environments_list(
        limit: int = None, cursor: str = None, sort: str = None
    ) -> Dict[str, Any]:
        """List all environments

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
            "GET", "environments", params=params
        )

    @mcp.tool()
    async def dct_environments_search(
        limit: int = None,
        cursor: str = None,
        sort: str = None,
        filter: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Search for environments with filters

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
            "environments/search",
            data={"filter": filter},
            params=params,
        )

    @mcp.tool()
    async def dct_environment_get(environment_id: str) -> Dict[str, Any]:
        """Get environment details

        Args:
            environment_id: Environment ID
        """
        return await client.make_request("GET", f"environments/{environment_id}")

    @mcp.tool()
    async def dct_environment_enable(environment_id: str) -> Dict[str, Any]:
        """Enable an environment

        Args:
            environment_id: Environment ID
        """
        return await client.make_request("POST", f"environments/{environment_id}/enable")

    @mcp.tool()
    async def dct_environment_disable(environment_id: str) -> Dict[str, Any]:
        """Disable an environment

        Args:
            environment_id: Environment ID
        """
        return await client.make_request("POST", f"environments/{environment_id}/disable")

    @mcp.tool()
    async def dct_environment_refresh(environment_id: str) -> Dict[str, Any]:
        """Refresh an environment (discover new databases/changes)

        Args:
            environment_id: Environment ID
        """
        return await client.make_request("POST", f"environments/{environment_id}/refresh")

    @mcp.tool()
    async def dct_environment_users_list(environment_id: str) -> Dict[str, Any]:
        """List users for an environment

        Args:
            environment_id: Environment ID
        """
        return await client.make_request("GET", f"environments/{environment_id}/users")

    @mcp.tool()
    async def dct_environments_compatible_repositories_by_snapshot(
        snapshot_id: str,
    ) -> Dict[str, Any]:
        """Get compatible repositories by snapshot for provisioning

        Args:
            snapshot_id: Snapshot ID to find compatible repositories for
        """
        data = {"snapshotId": snapshot_id}
        return await client.make_request(
            "POST", "environments/compatible_repositories_by_snapshot", data=data
        )

    @mcp.tool()
    async def dct_environments_compatible_repositories_by_timestamp(
        timeflow_id: str,
        timestamp: str,
    ) -> Dict[str, Any]:
        """Get compatible repositories by timestamp for provisioning

        Args:
            timeflow_id: Timeflow ID
            timestamp: Timestamp (ISO format)
        """
        data = {"timeflowId": timeflow_id, "timestamp": timestamp}
        return await client.make_request(
            "POST", "environments/compatible_repositories_by_timestamp", data=data
        )

    @mcp.tool()
    async def dct_environments_compatible_repositories_from_bookmark(
        bookmark_id: str,
    ) -> Dict[str, Any]:
        """Get compatible repositories from bookmark for provisioning

        Args:
            bookmark_id: Bookmark ID to find compatible repositories for
        """
        data = {"bookmarkId": bookmark_id}
        return await client.make_request(
            "POST", "environments/compatible_repositories_from_bookmark", data=data
        )

    logger.info("Environment tools registered successfully")

