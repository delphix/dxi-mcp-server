"""
VDB tools for DCT API
"""

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from ..client import DCTAPIClient

logger = logging.getLogger(__name__)


def register_vdb_tools(mcp: FastMCP, client: DCTAPIClient):
    """Register VDB-related tools"""

    @mcp.tool()
    async def dct_vdb_list(
        limit: int = None, cursor: str = None, sort: str = None
    ) -> Dict[str, Any]:
        """List all virtual databases (VDBs)

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
            "GET", "vdbs", params=params
        )

    @mcp.tool()
    async def dct_vdb_search(
        limit: int = None,
        cursor: str = None,
        sort: str = None,
        filter: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Search for virtual databases with filters

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
            "vdbs/search",
            data={"filter": filter},
            params=params,
        )

    @mcp.tool()
    async def dct_vdb_get(vdb_id: str) -> Dict[str, Any]:
        """Get virtual database details

        Args:
            vdb_id: Virtual Database ID
        """
        return await client.make_request("GET", f"vdbs/{vdb_id}")

    @mcp.tool()
    async def dct_vdb_provision_by_timestamp(
        source_id: str,
        target_environment_id: str,
        name: str,
        engine_id: str,
        timestamp: str = None,
        database_name: str = None,
        environment_user_id: str = None,
        auto_select_repository: bool = True,
    ) -> Dict[str, Any]:
        """Provision a new VDB by timestamp

        Args:
            source_id: Source database ID
            target_environment_id: Target environment ID
            name: VDB name
            engine_id: Engine ID
            timestamp: Timestamp to provision from (ISO format, optional - uses latest if not provided)
            database_name: Database name (optional)
            environment_user_id: Environment user ID (optional)
            auto_select_repository: Auto select repository (default: True)
        """
        data = {
            "sourceId": source_id,
            "targetEnvironmentId": target_environment_id,
            "name": name,
            "engineId": engine_id,
            "autoSelectRepository": auto_select_repository,
        }

        if timestamp:
            data["timestamp"] = timestamp
        if database_name:
            data["databaseName"] = database_name
        if environment_user_id:
            data["environmentUserId"] = environment_user_id

        return await client.make_request("POST", "vdbs/provision_by_timestamp", data=data)

    @mcp.tool()
    async def dct_vdb_provision_by_snapshot(
        source_id: str,
        target_environment_id: str,
        name: str,
        engine_id: str,
        snapshot_id: str,
        database_name: str = None,
        environment_user_id: str = None,
        auto_select_repository: bool = True,
    ) -> Dict[str, Any]:
        """Provision a new VDB by snapshot

        Args:
            source_id: Source database ID
            target_environment_id: Target environment ID
            name: VDB name
            engine_id: Engine ID
            snapshot_id: Snapshot ID to provision from
            database_name: Database name (optional)
            environment_user_id: Environment user ID (optional)
            auto_select_repository: Auto select repository (default: True)
        """
        data = {
            "sourceId": source_id,
            "targetEnvironmentId": target_environment_id,
            "name": name,
            "engineId": engine_id,
            "snapshotId": snapshot_id,
            "autoSelectRepository": auto_select_repository,
        }

        if database_name:
            data["databaseName"] = database_name
        if environment_user_id:
            data["environmentUserId"] = environment_user_id

        return await client.make_request("POST", "vdbs/provision_by_snapshot", data=data)

    @mcp.tool()
    async def dct_vdb_provision_from_bookmark(
        source_id: str,
        target_environment_id: str,
        name: str,
        engine_id: str,
        bookmark_id: str,
        database_name: str = None,
        environment_user_id: str = None,
        auto_select_repository: bool = True,
    ) -> Dict[str, Any]:
        """Provision a new VDB from bookmark

        Args:
            source_id: Source database ID
            target_environment_id: Target environment ID
            name: VDB name
            engine_id: Engine ID
            bookmark_id: Bookmark ID to provision from
            database_name: Database name (optional)
            environment_user_id: Environment user ID (optional)
            auto_select_repository: Auto select repository (default: True)
        """
        data = {
            "sourceId": source_id,
            "targetEnvironmentId": target_environment_id,
            "name": name,
            "engineId": engine_id,
            "bookmarkId": bookmark_id,
            "autoSelectRepository": auto_select_repository,
        }

        if database_name:
            data["databaseName"] = database_name
        if environment_user_id:
            data["environmentUserId"] = environment_user_id

        return await client.make_request("POST", "vdbs/provision_from_bookmark", data=data)

    @mcp.tool()
    async def dct_vdb_delete(vdb_id: str, force: bool = False) -> Dict[str, Any]:
        """Delete a virtual database

        Args:
            vdb_id: Virtual Database ID
            force: Force deletion even if dependencies exist
        """
        params = {"force": force}
        return await client.make_request(
            "DELETE", f"vdbs/{vdb_id}", params=params
        )

    @mcp.tool()
    async def dct_vdb_refresh_by_timestamp(
        vdb_id: str,
        timestamp: str = None,
    ) -> Dict[str, Any]:
        """Refresh a VDB by timestamp

        Args:
            vdb_id: Virtual Database ID
            timestamp: Timestamp to refresh to (ISO format, optional - uses latest if not provided)
        """
        data = {}
        if timestamp:
            data["timestamp"] = timestamp

        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/refresh_by_timestamp", data=data
        )

    @mcp.tool()
    async def dct_vdb_refresh_by_snapshot(
        vdb_id: str,
        snapshot_id: str,
    ) -> Dict[str, Any]:
        """Refresh a VDB by snapshot

        Args:
            vdb_id: Virtual Database ID
            snapshot_id: Snapshot ID to refresh from
        """
        data = {"snapshotId": snapshot_id}

        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/refresh_by_snapshot", data=data
        )

    @mcp.tool()
    async def dct_vdb_refresh_from_bookmark(
        vdb_id: str,
        bookmark_id: str,
    ) -> Dict[str, Any]:
        """Refresh a VDB from a bookmark

        Args:
            vdb_id: Virtual Database ID
            bookmark_id: Bookmark ID to refresh from
        """
        data = {"bookmarkId": bookmark_id}

        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/refresh_from_bookmark", data=data
        )

    @mcp.tool()
    async def dct_vdb_rollback_by_timestamp(
        vdb_id: str,
        timestamp: str,
    ) -> Dict[str, Any]:
        """Rollback a VDB by timestamp

        Args:
            vdb_id: Virtual Database ID
            timestamp: Timestamp to rollback to (ISO format)
        """
        data = {"timestamp": timestamp}

        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/rollback_by_timestamp", data=data
        )

    @mcp.tool()
    async def dct_vdb_rollback_by_snapshot(
        vdb_id: str,
        snapshot_id: str,
    ) -> Dict[str, Any]:
        """Rollback a VDB by snapshot

        Args:
            vdb_id: Virtual Database ID
            snapshot_id: Snapshot ID to rollback to
        """
        data = {"snapshotId": snapshot_id}

        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/rollback_by_snapshot", data=data
        )

    @mcp.tool()
    async def dct_vdb_rollback_from_bookmark(
        vdb_id: str,
        bookmark_id: str,
    ) -> Dict[str, Any]:
        """Rollback a VDB from a bookmark

        Args:
            vdb_id: Virtual Database ID
            bookmark_id: Bookmark ID to rollback from
        """
        data = {"bookmarkId": bookmark_id}

        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/rollback_from_bookmark", data=data
        )

    @mcp.tool()
    async def dct_vdb_start(vdb_id: str) -> Dict[str, Any]:
        """Start a VDB

        Args:
            vdb_id: Virtual Database ID
        """
        return await client.make_request("POST", f"vdbs/{vdb_id}/start")

    @mcp.tool()
    async def dct_vdb_stop(vdb_id: str) -> Dict[str, Any]:
        """Stop a VDB

        Args:
            vdb_id: Virtual Database ID
        """
        return await client.make_request("POST", f"vdbs/{vdb_id}/stop")

    @mcp.tool()
    async def dct_vdb_enable(vdb_id: str) -> Dict[str, Any]:
        """Enable a VDB

        Args:
            vdb_id: Virtual Database ID
        """
        return await client.make_request("POST", f"vdbs/{vdb_id}/enable")

    @mcp.tool()
    async def dct_vdb_disable(vdb_id: str) -> Dict[str, Any]:
        """Disable a VDB

        Args:
            vdb_id: Virtual Database ID
        """
        return await client.make_request("POST", f"vdbs/{vdb_id}/disable")

    @mcp.tool()
    async def dct_vdb_lock(vdb_id: str) -> Dict[str, Any]:
        """Lock a VDB

        Args:
            vdb_id: Virtual Database ID
        """
        return await client.make_request("POST", f"vdbs/{vdb_id}/lock")

    @mcp.tool()
    async def dct_vdb_unlock(vdb_id: str) -> Dict[str, Any]:
        """Unlock a VDB

        Args:
            vdb_id: Virtual Database ID
        """
        return await client.make_request("POST", f"vdbs/{vdb_id}/unlock")

    @mcp.tool()
    async def dct_vdb_refresh_by_location(
        vdb_id: str,
        location: str,
    ) -> Dict[str, Any]:
        """Refresh a VDB by location/SCN

        Args:
            vdb_id: Virtual Database ID
            location: Location/SCN to refresh to
        """
        data = {"location": location}

        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/refresh_by_location", data=data
        )

    @mcp.tool()
    async def dct_vdb_snapshot(
        vdb_id: str, name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a snapshot of a virtual database

        Args:
            vdb_id: Virtual Database ID
            name: Snapshot name
        """
        data = {}
        if name:
            data["name"] = name

        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/snapshots", data=data
        )

    @mcp.tool()
    async def dct_vdb_snapshots_list(
        vdb_id: str, limit: int = None, cursor: str = None
    ) -> Dict[str, Any]:
        """List snapshots for a virtual database

        Args:
            vdb_id: Virtual Database ID
            limit: Maximum number of results to return
            cursor: Pagination cursor
        """
        params = {}
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor

        return await client.make_request(
            "GET", f"vdbs/{vdb_id}/snapshots", params=params
        )

    logger.info("VDB tools registered successfully")
