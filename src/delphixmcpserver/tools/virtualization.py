"""
Virtualization tools for DCT API
"""

from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from ..client import DCTAPIClient


def register_virtualization_tools(mcp: FastMCP, client: DCTAPIClient):
    """Register virtualization-related tools"""

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
            "GET", "virtualization/databases", params=params
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
            "virtualization/databases/search",
            data={"filter": filter},
            params=params,
        )

    @mcp.tool()
    async def dct_vdb_get(vdb_id: str) -> Dict[str, Any]:
        """Get virtual database details

        Args:
            vdb_id: Virtual Database ID
        """
        return await client.make_request("GET", f"virtualization/databases/{vdb_id}")

    @mcp.tool()
    async def dct_vdb_create(
        source_id: str,
        target_environment_id: str,
        name: str,
        engine_id: str,
        database_name: str = None,
        environment_user_id: str = None,
        auto_select_repository: bool = True,
    ) -> Dict[str, Any]:
        """Create a new virtual database

        Args:
            source_id: Source database ID
            target_environment_id: Target environment ID
            name: VDB name
            engine_id: Engine ID
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

        if database_name:
            data["databaseName"] = database_name
        if environment_user_id:
            data["environmentUserId"] = environment_user_id

        return await client.make_request("POST", "virtualization/databases", data=data)

    @mcp.tool()
    async def dct_vdb_delete(vdb_id: str, force: bool = False) -> Dict[str, Any]:
        """Delete a virtual database

        Args:
            vdb_id: Virtual Database ID
            force: Force deletion even if dependencies exist
        """
        params = {"force": force}
        return await client.make_request(
            "DELETE", f"virtualization/databases/{vdb_id}", params=params
        )

    @mcp.tool()
    async def dct_vdb_refresh(
        vdb_id: str,
        snapshot_id: Optional[str] = None,
        bookmark_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Refresh a virtual database

        Args:
            vdb_id: Virtual Database ID
            snapshot_id: Snapshot ID to refresh from
            bookmark_id: Bookmark ID to refresh from
        """
        data = {}
        if snapshot_id:
            data["snapshotId"] = snapshot_id
        if bookmark_id:
            data["bookmarkId"] = bookmark_id

        return await client.make_request(
            "POST", f"virtualization/databases/{vdb_id}/refresh", data=data
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
            "POST", f"virtualization/databases/{vdb_id}/snapshots", data=data
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
            "GET", f"virtualization/databases/{vdb_id}/snapshots", params=params
        )
