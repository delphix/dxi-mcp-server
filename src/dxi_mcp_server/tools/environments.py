"""
Environment tools for DCT API

Schema summaries (key fields only):
- Environment:
  - id, name, description, os_type [UNIX|WINDOWS]
  - engine_id, namespace_id, namespace_name, namespace
  - enabled, encryption_enabled, is_cluster, cluster_home, cluster_name
  - scan, remote_listener, is_windows_target, staging_environment
  - hosts[] (Host), repositories[] (Repository), listeners[] (OracleListener)
  - env_users[] (EnvironmentUser), tags[]
- EnvironmentUser (list_environment_users):
  - user_ref, username, primary_user, auth_type
- Job (enable/disable/refresh): see vdb module notes
- Compatible repositories endpoints return items: Environment[]
- PaginatedResponseMetadata: prev_cursor, next_cursor, total
"""

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from ..client import DCTAPIClient

logger = logging.getLogger(__name__)


def register_environment_tools(mcp: FastMCP, client: DCTAPIClient):
    """Register Environment-related tools"""

    @mcp.tool()
    async def list_environments(
            limit: Optional[int] = None,
            cursor: Optional[str] = None,
            sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List all environments

        Args:
            limit: Maximum number of results to return
            cursor: Pagination cursor
            sort: Sort order
        Returns:
            Object with:
            - items: list of Environment objects
            - errors: optional Errors object
            - response_metadata: pagination metadata
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
    async def search_environments(
        filter_expression: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search for environments with filter expressions

        Args:
            filter_expression: Filter expression string (e.g., "name CONTAINS 'prod' AND status EQ 'online'")
            limit: Maximum number of results to return
            cursor: Pagination cursor
            sort: Sort order

        Available filterable fields:
            - name
            - namespace
            - is_cluster
            - cluster_home
            - cluster_name
            - scan
            - remote_listener
            - is_windows_target
            - staging_environment
            - enabled
            - encryption_enabled
            - description
            - namespace_id
            - namespace_name
            - is_replica
            - hosts (hostname, os_name, os_version, memory_size, available, available_timestamp, not_available_reason, nfs_addresses, dsp_keystore_alias, dsp_keystore_path, dsp_truststore_path, java_home, ssh_port, toolkit_path, connector_port, connector_version)

        Literal values (per API docs):
            - Nil: nil (case-insensitive)
            - Boolean: true, false (unquoted)
            - Number: 0, 1, -1, 1.2, 1.2e-2 (unquoted)
            - String: quoted, e.g., 'foo', "bar"
            - Datetime: RFC3339 literal without quotes, e.g., 2018-04-27T18:39:26.397237+00:00
            - List: [0], [0, 1], ['foo', "bar"]

        Important:
            - Quote strings; do NOT quote datetimes.
            - Example: available_timestamp GE 2024-01-01T00:00:00.000Z

        Returns:
            Object with:
            - items: list of Environment objects
            - response_metadata: pagination metadata
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
                "environments/search",
                params=params,
                json=search_body,
            )
            logger.info(
                f"Found {len(result.get('items', []))} environments matching filter expression"
            )
            return result

        except Exception as e:
            logger.error(f"Error searching environments: {str(e)}")
            raise

    @mcp.tool()
    async def get_environment(environment_id: str) -> Dict[str, Any]:
        """Get environment details

        Args:
            environment_id: Environment ID
        Returns:
            Environment object
        """
        return await client.make_request("GET", f"environments/{environment_id}")

    @mcp.tool()
    async def enable_environment(environment_id: str) -> Dict[str, Any]:
        """Enable an environment

        Args:
            environment_id: Environment ID
        Returns:
            Object with:
            - job: Job object indicating enable initiated
        """
        return await client.make_request("POST", f"environments/{environment_id}/enable")

    @mcp.tool()
    async def disable_environment(environment_id: str) -> Dict[str, Any]:
        """Disable an environment

        Args:
            environment_id: Environment ID
        Returns:
            Object with:
            - job: Job object indicating disable initiated
        """
        return await client.make_request("POST", f"environments/{environment_id}/disable")

    @mcp.tool()
    async def refresh_environment(environment_id: str) -> Dict[str, Any]:
        """Refresh an environment (discover new databases/changes)

        Args:
            environment_id: Environment ID
        Returns:
            Object with:
            - job: Job object indicating refresh initiated
        """
        return await client.make_request("POST", f"environments/{environment_id}/refresh")

    @mcp.tool()
    async def list_environment_users(environment_id: str) -> Dict[str, Any]:
        """List users for an environment

        Args:
            environment_id: Environment ID
        Returns:
            Object with:
            - items: list of EnvironmentUser objects or user descriptors
        """
        return await client.make_request("GET", f"environments/{environment_id}/users")

    @mcp.tool()
    async def compatible_repos_by_snapshot(
        snapshot_id: str,
    ) -> Dict[str, Any]:
        """Get compatible repositories by snapshot for provisioning

        Args:
            snapshot_id: Snapshot ID to find compatible repositories for
        Returns:
            Object with:
            - items: list of Environment objects compatible with snapshot
        """
        data = {"snapshot_id": snapshot_id}
        return await client.make_request(
            "POST", "environments/compatible_repositories_by_snapshot", json=data
        )

    @mcp.tool()
    async def compatible_repos_by_timestamp(
        timeflow_id: str,
        timestamp: str,
    ) -> Dict[str, Any]:
        """Get compatible repositories by timestamp for provisioning

        Args:
            timeflow_id: Timeflow ID
            timestamp: Timestamp (ISO format)
        Returns:
            Object with:
            - items: list of Environment objects compatible with timestamp
        """
        data = {"timeflow_id": timeflow_id, "timestamp": timestamp}
        return await client.make_request(
            "POST", "environments/compatible_repositories_by_timestamp", json=data
        )

    @mcp.tool()
    async def compatible_repos_from_bookmark(
        bookmark_id: str,
    ) -> Dict[str, Any]:
        """Get compatible repositories from bookmark for provisioning

        Args:
            bookmark_id: Bookmark ID to find compatible repositories for
        Returns:
            Object with:
            - items: list of Environment objects compatible with bookmark
        """
        data = {"bookmark_id": bookmark_id}
        return await client.make_request(
            "POST", "environments/compatible_repositories_from_bookmark", json=data
        )

    logger.info("Environment tools registered successfully")

