"""
VDB tools for DCT API

Schema summaries (key fields only):
- VDB:
  - id, name, database_type, database_name
  - engine_id, engine_name, environment_id, fqdn, ip_address
  - status, size, storage_size, masked, content_type
  - namespace_id, namespace_name, group_name, cdb_id
  - parent_id, parent_dsource_id, root_parent_id
  - current_timeflow_id, previous_timeflow_id, last_refreshed_date
  - parent_timeflow_timestamp, parent_timeflow_timezone
  - tags[], creation_date, mount_point
- Job (async operation result):
  - id, status [PENDING|STARTED|RUNNING|WAITING|COMPLETED|FAILED|...]
  - target_id, target_name, start_time, update_time
  - error_details, warning_message, percent_complete, tasks[]
- Snapshot (for list_vdb_snapshots):
  - id, dataset_id, name, engine_id
  - timestamp, location, creation_time
  - consistency, missing_non_logged_data, timezone, version
  - expiration, retain_forever, effective_expiration, effective_retain_forever
  - tags[]
- PaginatedResponseMetadata:
  - prev_cursor, next_cursor, total
"""

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from ..client import DCTAPIClient

logger = logging.getLogger(__name__)


def register_vdb_tools(mcp: FastMCP, client: DCTAPIClient):
    """Register VDB-related tools"""

    @mcp.tool()
    async def list_vdbs(
        limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all virtual databases (VDBs)

        Args:
            limit: Maximum number of results to return
            cursor: Pagination cursor
            sort: Sort order

        Returns:
            Object with:
            - items: list of VDB objects
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
            "GET", "vdbs", params=params
        )

    @mcp.tool()
    async def search_vdbs(
        filter_expression: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search for virtual databases with filter expressions

        Args:
            filter_expression: Filter expression string (e.g., "name CONTAINS 'test' AND status EQ 'running'")
            limit: Maximum number of results to return
            cursor: Pagination cursor
            sort: Sort order

        Available filterable fields:
            - id
            - database_type
            - name
            - database_name
            - database_version
            - jdbc_connection_string
            - size
            - storage_size
            - engine_id
            - status
            - environment_id
            - ip_address
            - fqdn
            - parent_id
            - parent_dsource_id
            - group_name
            - creation_date
            - enabled
            - engine_name
            - cdb_id
            - pluggable_database_id
            - container_name
            - namespace_id
            - namespace_name
            - is_replica
            - is_locked
            - exported_data_directory
            - vcdb_exported_data_directory
            - locked_by
            - locked_by_name
            - content_type
            - tags (key, value)

        Literal values (per API docs):
            - Nil: nil (case-insensitive)
            - Boolean: true, false (unquoted)
            - Number: 0, 1, -1, 1.2, 1.2e-2 (unquoted)
            - String: quoted, e.g., 'foo', "bar"
            - Datetime: RFC3339 literal without quotes, e.g., 2018-04-27T18:39:26.397237+00:00
            - List: [0], [0, 1], ['foo', "bar"]

        Important:
            - Quote strings; do NOT quote datetimes.
            - Example: creation_date GE 2024-01-01T00:00:00.000Z

        Returns:
            Object with:
            - items: list of VDB objects
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
                "vdbs/search",
                params=params,
                json=search_body,
            )
            logger.info(
                f"Found {len(result.get('items', []))} VDBs matching filter expression"
            )
            return result

        except Exception as e:
            logger.error(f"Error searching VDBs: {str(e)}")
            raise

    @mcp.tool()
    async def get_vdb(vdb_id: str) -> Dict[str, Any]:
        """Get virtual database details

        Args:
            vdb_id: Virtual Database ID

        Returns:
            VDB object
        """
        return await client.make_request("GET", f"vdbs/{vdb_id}")

    @mcp.tool()
    async def provision_vdb_by_timestamp(
        source_data_id: str,
        name: Optional[str] = None,
        engine_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        timestamp_in_database_timezone: Optional[str] = None,
        timeflow_id: Optional[str] = None,
        database_name: Optional[str] = None,
        environment_user_id: Optional[str] = None,
        auto_select_repository: Optional[bool] = True,
        target_group_id: Optional[str] = None,
        repository_id: Optional[str] = None,
        make_current_account_owner: Optional[bool] = None,
        mount_point: Optional[str] = None,
        postgres_port: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Provision a new VDB by timestamp

        Args:
            source_data_id: Source database ID
            target_environment_id: Target environment ID
            name: VDB name
            engine_id: Engine ID
            timestamp: Timestamp to provision from (ISO format, optional - uses latest if not provided)
            database_name: Database name (optional)
            environment_user_id: Environment user ID (optional)
            auto_select_repository: Auto select repository (default: True)
            mount_point: Mount point for the VDB (required for some database types)
            postgres_port: Port number for PostgreSQL target database (PostgreSQL only)
        Returns:
            ProvisionVDBResponse object with:
            - job: Job object
            - vdb: optional VDB object or identifier depending on API schema
        """
        data: Dict[str, Any] = {
            "source_data_id": source_data_id,
        }

        if name is not None:
            data["name"] = name
        if engine_id is not None:
            data["engine_id"] = engine_id
        if timestamp is not None:
            data["timestamp"] = timestamp
        if timestamp_in_database_timezone is not None:
            data["timestamp_in_database_timezone"] = timestamp_in_database_timezone
        if timeflow_id is not None:
            data["timeflow_id"] = timeflow_id
        if database_name is not None:
            data["database_name"] = database_name
        if environment_user_id is not None:
            data["environment_user_id"] = environment_user_id
        if auto_select_repository is not None:
            data["auto_select_repository"] = auto_select_repository
        if target_group_id is not None:
            data["target_group_id"] = target_group_id
        if repository_id is not None:
            data["repository_id"] = repository_id
        if make_current_account_owner is not None:
            data["make_current_account_owner"] = make_current_account_owner
        if mount_point is not None:
            data["mount_point"] = mount_point
        if postgres_port is not None:
            data["postgres_port"] = postgres_port

        return await client.make_request("POST", "vdbs/provision_by_timestamp", json=data)

    @mcp.tool()
    async def provision_vdb_by_snapshot(
        snapshot_id: str,
        source_data_id: Optional[str] = None,
        name: Optional[str] = None,
        engine_id: Optional[str] = None,
        database_name: Optional[str] = None,
        environment_user_id: Optional[str] = None,
        auto_select_repository: Optional[bool] = True,
        target_group_id: Optional[str] = None,
        repository_id: Optional[str] = None,
        make_current_account_owner: Optional[bool] = None,
        mount_point: Optional[str] = None,
        postgres_port: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Provision a new VDB by snapshot

        Args:
            source_data_id: Source database ID
            target_environment_id: Target environment ID
            name: VDB name
            engine_id: Engine ID
            snapshot_id: Snapshot ID to provision from
            database_name: Database name (optional)
            environment_user_id: Environment user ID (optional)
            auto_select_repository: Auto select repository (default: True)
            mount_point: Mount point for the VDB (required for some database types)
            postgres_port: Port number for PostgreSQL target database (PostgreSQL only)
        Returns:
            ProvisionVDBResponse object with:
            - job: Job object
            - vdb: optional VDB object or identifier depending on API schema
        """
        data: Dict[str, Any] = {
            "snapshot_id": snapshot_id,
        }

        if source_data_id is not None:
            data["source_data_id"] = source_data_id
        if name is not None:
            data["name"] = name
        if engine_id is not None:
            data["engine_id"] = engine_id
        if database_name is not None:
            data["database_name"] = database_name
        if environment_user_id is not None:
            data["environment_user_id"] = environment_user_id
        if auto_select_repository is not None:
            data["auto_select_repository"] = auto_select_repository
        if target_group_id is not None:
            data["target_group_id"] = target_group_id
        if repository_id is not None:
            data["repository_id"] = repository_id
        if make_current_account_owner is not None:
            data["make_current_account_owner"] = make_current_account_owner
        if mount_point is not None:
            data["mount_point"] = mount_point
        if postgres_port is not None:
            data["postgres_port"] = postgres_port

        return await client.make_request("POST", "vdbs/provision_by_snapshot", json=data)

    @mcp.tool()
    async def provision_vdb_from_bookmark(
        bookmark_id: str,
        name: Optional[str] = None,
        engine_id: Optional[str] = None,
        database_name: Optional[str] = None,
        environment_user_id: Optional[str] = None,
        auto_select_repository: Optional[bool] = True,
        target_group_id: Optional[str] = None,
        repository_id: Optional[str] = None,
        make_current_account_owner: Optional[bool] = None,
        mount_point: Optional[str] = None,
        postgres_port: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Provision a new VDB from bookmark

        Args:
            bookmark_id: Bookmark ID to provision from
            target_environment_id: Target environment ID
            name: VDB name
            engine_id: Engine ID
            database_name: Database name (optional)
            environment_user_id: Environment user ID (optional)
            auto_select_repository: Auto select repository (default: True)
            mount_point: Mount point for the VDB (required for some database types)
            postgres_port: Port number for PostgreSQL target database (PostgreSQL only)
        Returns:
            ProvisionVDBResponse object with:
            - job: Job object
            - vdb: optional VDB object or identifier depending on API schema
        """
        data: Dict[str, Any] = {
            "bookmark_id": bookmark_id,
        }

        if name is not None:
            data["name"] = name
        if engine_id is not None:
            data["engine_id"] = engine_id
        if database_name is not None:
            data["database_name"] = database_name
        if environment_user_id is not None:
            data["environment_user_id"] = environment_user_id
        if auto_select_repository is not None:
            data["auto_select_repository"] = auto_select_repository
        if target_group_id is not None:
            data["target_group_id"] = target_group_id
        if repository_id is not None:
            data["repository_id"] = repository_id
        if make_current_account_owner is not None:
            data["make_current_account_owner"] = make_current_account_owner
        if mount_point is not None:
            data["mount_point"] = mount_point
        if postgres_port is not None:
            data["postgres_port"] = postgres_port

        return await client.make_request("POST", "vdbs/provision_from_bookmark", json=data)

    @mcp.tool()
    async def provision_vdb_by_snapshot_defaults(
        snapshot_id: Optional[str] = None,
        engine_id: Optional[str] = None,
        source_data_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get default provision parameters for provisioning a new VDB by snapshot

        Args:
            snapshot_id: Snapshot ID to provision from
            engine_id: Engine ID (optional)
            source_data_id: Source database ID (optional)
        Returns:
            Default ProvisionVDBBySnapshotParameters object
        """
        body: Dict[str, Any] = {}
        if snapshot_id is not None:
            body["snapshot_id"] = snapshot_id
        if engine_id is not None:
            body["engine_id"] = engine_id
        if source_data_id is not None:
            body["source_data_id"] = source_data_id

        return await client.make_request(
            "POST", "vdbs/provision_by_snapshot/defaults", json=body
        )

    @mcp.tool()
    async def provision_vdb_by_timestamp_defaults(
        source_data_id: str,
        timestamp: Optional[str] = None,
        timestamp_in_database_timezone: Optional[str] = None,
        timeflow_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get default provision parameters for provisioning a new VDB by timestamp

        Args:
            source_data_id: Source database ID
            timestamp: Timestamp (optional)
            timestamp_in_database_timezone: Timestamp in DB timezone (optional)
            timeflow_id: Timeflow ID (optional)
        Returns:
            Default ProvisionVDBByTimestampParameters object
        """
        body: Dict[str, Any] = {"source_data_id": source_data_id}
        if timestamp is not None:
            body["timestamp"] = timestamp
        if timestamp_in_database_timezone is not None:
            body["timestamp_in_database_timezone"] = timestamp_in_database_timezone
        if timeflow_id is not None:
            body["timeflow_id"] = timeflow_id

        return await client.make_request(
            "POST", "vdbs/provision_by_timestamp/defaults", json=body
        )

    @mcp.tool()
    async def provision_vdb_from_bookmark_defaults(
        bookmark_id: str,
    ) -> Dict[str, Any]:
        """Get default provision parameters for provisioning a new VDB from a bookmark

        Args:
            bookmark_id: Bookmark ID to provision from
        Returns:
            Default ProvisionVDBFromBookmarkParameters object
        """
        body: Dict[str, Any] = {"bookmark_id": bookmark_id}

        return await client.make_request(
            "POST", "vdbs/provision_from_bookmark/defaults", json=body
        )

    @mcp.tool()
    async def delete_vdb(
        vdb_id: str,
        force: bool = False,
        delete_all_dependent_vdbs: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Delete a virtual database

        Args:
            vdb_id: Virtual Database ID
            force: Force deletion even if dependencies exist
        Returns:
            Object with:
            - job: Job object indicating deletion initiated
        """
        body: Dict[str, Any] = {"force": force}
        if delete_all_dependent_vdbs is not None:
            body["delete_all_dependent_vdbs"] = delete_all_dependent_vdbs
        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/delete", json=body
        )

    @mcp.tool()
    async def refresh_vdb_by_timestamp(
        vdb_id: str,
        timestamp: Optional[str] = None,
        timestamp_in_database_timezone: Optional[str] = None,
        timeflow_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Refresh a VDB by timestamp

        Args:
            vdb_id: Virtual Database ID
            timestamp: Timestamp to refresh to (ISO format, optional - uses latest if not provided)
        Returns:
            Object with:
            - job: Job object indicating refresh initiated
        """
        data: Dict[str, Any] = {}
        if timestamp is not None:
            data["timestamp"] = timestamp
        if timestamp_in_database_timezone is not None:
            data["timestamp_in_database_timezone"] = timestamp_in_database_timezone
        if timeflow_id is not None:
            data["timeflow_id"] = timeflow_id

        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/refresh_by_timestamp", json=data
        )

    @mcp.tool()
    async def refresh_vdb_by_snapshot(
        vdb_id: str,
        snapshot_id: str,
    ) -> Dict[str, Any]:
        """Refresh a VDB by snapshot

        Args:
            vdb_id: Virtual Database ID
            snapshot_id: Snapshot ID to refresh from
        Returns:
            Object with:
            - job: Job object indicating refresh initiated
        """
        data = {"snapshot_id": snapshot_id}

        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/refresh_by_snapshot", json=data
        )

    @mcp.tool()
    async def refresh_vdb_from_bookmark(
        vdb_id: str,
        bookmark_id: str,
    ) -> Dict[str, Any]:
        """Refresh a VDB from a bookmark

        Args:
            vdb_id: Virtual Database ID
            bookmark_id: Bookmark ID to refresh from
        Returns:
            Object with:
            - job: Job object indicating refresh initiated
        """
        data = {"bookmark_id": bookmark_id}

        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/refresh_from_bookmark", json=data
        )

    @mcp.tool()
    async def rollback_vdb_by_timestamp(
        vdb_id: str,
        timestamp: str,
    ) -> Dict[str, Any]:
        """Rollback a VDB by timestamp

        Args:
            vdb_id: Virtual Database ID
            timestamp: Timestamp to rollback to (ISO format)
        Returns:
            Object with:
            - job: Job object indicating rollback initiated
        """
        data = {"timestamp": timestamp}

        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/rollback_by_timestamp", json=data
        )

    @mcp.tool()
    async def rollback_vdb_by_snapshot(
        vdb_id: str,
        snapshot_id: str,
    ) -> Dict[str, Any]:
        """Rollback a VDB by snapshot

        Args:
            vdb_id: Virtual Database ID
            snapshot_id: Snapshot ID to rollback to
        Returns:
            Object with:
            - job: Job object indicating rollback initiated
        """
        data = {"snapshot_id": snapshot_id}

        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/rollback_by_snapshot", json=data
        )

    @mcp.tool()
    async def rollback_vdb_from_bookmark(
        vdb_id: str,
        bookmark_id: str,
    ) -> Dict[str, Any]:
        """Rollback a VDB from a bookmark

        Args:
            vdb_id: Virtual Database ID
            bookmark_id: Bookmark ID to rollback from
        Returns:
            Object with:
            - job: Job object indicating rollback initiated
        """
        data = {"bookmark_id": bookmark_id}

        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/rollback_from_bookmark", json=data
        )

    @mcp.tool()
    async def start_vdb(vdb_id: str) -> Dict[str, Any]:
        """Start a VDB

        Args:
            vdb_id: Virtual Database ID
        Returns:
            Object with:
            - job: Job object indicating start initiated
        """
        return await client.make_request("POST", f"vdbs/{vdb_id}/start")

    @mcp.tool()
    async def stop_vdb(vdb_id: str) -> Dict[str, Any]:
        """Stop a VDB

        Args:
            vdb_id: Virtual Database ID
        Returns:
            Object with:
            - job: Job object indicating stop initiated
        """
        return await client.make_request("POST", f"vdbs/{vdb_id}/stop")

    @mcp.tool()
    async def enable_vdb(vdb_id: str) -> Dict[str, Any]:
        """Enable a VDB

        Args:
            vdb_id: Virtual Database ID
        Returns:
            Object with:
            - job: Job object indicating enable initiated
        """
        return await client.make_request("POST", f"vdbs/{vdb_id}/enable")

    @mcp.tool()
    async def disable_vdb(vdb_id: str) -> Dict[str, Any]:
        """Disable a VDB

        Args:
            vdb_id: Virtual Database ID
        Returns:
            Object with:
            - job: Job object indicating disable initiated
        """
        return await client.make_request("POST", f"vdbs/{vdb_id}/disable")

    @mcp.tool()
    async def lock_vdb(vdb_id: str) -> Dict[str, Any]:
        """Lock a VDB

        Args:
            vdb_id: Virtual Database ID
        Returns:
            Object with:
            - job: Job object indicating lock initiated
        """
        return await client.make_request("POST", f"vdbs/{vdb_id}/lock")

    @mcp.tool()
    async def unlock_vdb(vdb_id: str) -> Dict[str, Any]:
        """Unlock a VDB

        Args:
            vdb_id: Virtual Database ID
        Returns:
            Object with:
            - job: Job object indicating unlock initiated
        """
        return await client.make_request("POST", f"vdbs/{vdb_id}/unlock")

    @mcp.tool()
    async def refresh_vdb_by_location(
        vdb_id: str,
        location: str,
    ) -> Dict[str, Any]:
        """Refresh a VDB by location/SCN

        Args:
            vdb_id: Virtual Database ID
            location: Location/SCN to refresh to
        Returns:
            Object with:
            - job: Job object indicating refresh initiated
        """
        data = {"location": location}

        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/refresh_by_location", data=data
        )

    @mcp.tool()
    async def snapshot_vdb(
        vdb_id: str, name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a snapshot of a virtual database

        Args:
            vdb_id: Virtual Database ID
            name: Snapshot name
        Returns:
            Object with:
            - job: Job object indicating snapshot initiated
        """
        data = {}
        if name:
            data["name"] = name

        return await client.make_request(
            "POST", f"vdbs/{vdb_id}/snapshots", json=data
        )

    @mcp.tool()
    async def list_vdb_snapshots(
        vdb_id: str, limit: int = None, cursor: str = None
    ) -> Dict[str, Any]:
        """List snapshots for a virtual database

        Args:
            vdb_id: Virtual Database ID
            limit: Maximum number of results to return
            cursor: Pagination cursor
        Returns:
            Object with:
            - items: list of Snapshot objects
            - response_metadata: pagination metadata
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
