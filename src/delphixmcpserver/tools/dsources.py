"""
DSources (Data Sources) API tools for DCT MCP Server

This module provides tools for managing dSources in the Delphix DCT API.
dSources are physical databases or datasets that serve as the source for virtual databases.
"""

import logging
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from ..client import DCTAPIClient

logger = logging.getLogger(__name__)


def register_dsource_tools(app: FastMCP, client: DCTAPIClient) -> None:
    """Register all dSource-related tools with the FastMCP app"""

    @app.tool()
    async def dct_dsources_list(
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List all dSources.

        Args:
            limit: Maximum number of items to return (default: 100)
            cursor: Cursor for pagination
            sort: Sort order (e.g., 'name', 'creation_date', 'database_type')

        Returns:
            Dictionary containing the list of dSources and pagination metadata
        """
        try:
            params = {}
            if limit is not None:
                params["limit"] = limit
            if cursor:
                params["cursor"] = cursor
            if sort:
                params["sort"] = sort

            result = await client.make_request("GET", "/dsources", params=params)
            logger.info(f"Listed {len(result.get('items', []))} dSources")
            return result

        except Exception as e:
            logger.error(f"Error listing dSources: {str(e)}")
            raise

    @app.tool()
    async def dct_dsources_search(
        search_criteria: Dict[str, Any],
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search for dSources using filters.

        Args:
            search_criteria: Search filters (e.g., {"name": "prod-db", "database_type": "oracle"})
            limit: Maximum number of items to return
            cursor: Cursor for pagination
            sort: Sort order

        Available search filters:
            - id: dSource ID
            - data_uuid: Data UUID
            - database_type: Database type (oracle, postgres, mysql, etc.)
            - name: dSource name
            - database_version: Database version
            - storage_size: Storage size in bytes
            - plugin_version: Plugin version
            - creation_date: Creation date
            - group_name: Group name
            - enabled: Boolean indicating if enabled
            - engine_id: Engine ID
            - source_id: Source ID
            - status: dSource status
            - engine_name: Engine name
            - cdb_id: Container database ID (for Oracle)

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
            search_body = {"filter_expression": search_criteria}

            result = await client.make_request(
                "POST", "/dsources/search", params=params, json=search_body
            )
            logger.info(
                f"Found {len(result.get('items', []))} dSources matching search criteria"
            )
            return result

        except Exception as e:
            logger.error(f"Error searching dSources: {str(e)}")
            raise

    @app.tool()
    async def dct_dsources_get(dsource_id: str) -> Dict[str, Any]:
        """
        Get a specific dSource by ID.

        Args:
            dsource_id: The ID of the dSource to retrieve

        Returns:
            Dictionary containing the dSource details
        """
        try:
            result = await client.make_request("GET", f"/dsources/{dsource_id}")
            logger.info(f"Retrieved dSource: {dsource_id}")
            return result

        except Exception as e:
            logger.error(f"Error getting dSource {dsource_id}: {str(e)}")
            raise

    @app.tool()
    async def dct_dsources_snapshots_list(
        dsource_id: str, limit: Optional[int] = None, cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List snapshots for a specific dSource.

        Args:
            dsource_id: The ID of the dSource
            limit: Maximum number of snapshots to return
            cursor: Cursor for pagination

        Returns:
            Dictionary containing the list of snapshots for the dSource
        """
        try:
            params = {}
            if limit is not None:
                params["limit"] = limit
            if cursor:
                params["cursor"] = cursor

            result = await client.make_request(
                "GET", f"/dsources/{dsource_id}/snapshots", params=params
            )
            logger.info(
                f"Listed {len(result.get('items', []))} snapshots for dSource {dsource_id}"
            )
            return result

        except Exception as e:
            logger.error(f"Error listing snapshots for dSource {dsource_id}: {str(e)}")
            raise

    @app.tool()
    async def dct_dsources_snapshot_create(
        dsource_id: str,
        skip_space_check: Optional[bool] = None,
        force_full_backup: Optional[str] = None,
        double_sync: Optional[bool] = None,
        mssql_backup_uuid: Optional[str] = None,
        sync_strategy: Optional[str] = None,
        ase_backup_files: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a snapshot of a dSource.

        Args:
            dsource_id: The ID of the dSource to snapshot
            skip_space_check: Skip space check (Oracle)
            force_full_backup: Force full backup (Oracle)
            double_sync: Perform double sync (Oracle)
            mssql_backup_uuid: Specific backup UUID for SQL Server
            sync_strategy: Sync strategy ('specific_backup' or default)
            ase_backup_files: List of backup files for ASE

        Returns:
            Dictionary containing the job information for the snapshot operation
        """
        try:
            snapshot_params = {}

            # Oracle-specific parameters
            if skip_space_check is not None:
                snapshot_params["skip_space_check"] = skip_space_check
            if force_full_backup is not None:
                snapshot_params["force_full_backup"] = force_full_backup
            if double_sync is not None:
                snapshot_params["double_sync"] = double_sync

            # SQL Server-specific parameters
            if mssql_backup_uuid is not None:
                snapshot_params["mssql_backup_uuid"] = mssql_backup_uuid

            # ASE-specific parameters
            if ase_backup_files is not None:
                snapshot_params["ase_backup_files"] = ase_backup_files

            # Sync strategy
            if sync_strategy is not None:
                snapshot_params["sync_strategy"] = sync_strategy

            result = await client.make_request(
                "POST", f"/dsources/{dsource_id}/snapshots", json=snapshot_params
            )
            logger.info(f"Initiated snapshot for dSource {dsource_id}")
            return result

        except Exception as e:
            logger.error(f"Error creating snapshot for dSource {dsource_id}: {str(e)}")
            raise

    @app.tool()
    async def dct_dsources_tags_get(dsource_id: str) -> Dict[str, Any]:
        """
        Get tags for a dSource.

        Args:
            dsource_id: The ID of the dSource

        Returns:
            Dictionary containing the tags for the dSource
        """
        try:
            result = await client.make_request("GET", f"/dsources/{dsource_id}/tags")
            logger.info(f"Retrieved tags for dSource: {dsource_id}")
            return result

        except Exception as e:
            logger.error(f"Error getting tags for dSource {dsource_id}: {str(e)}")
            raise

    @app.tool()
    async def dct_dsources_tags_create(
        dsource_id: str, tags: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Create tags for a dSource.

        Args:
            dsource_id: The ID of the dSource
            tags: List of tag objects with 'key' and 'value' properties

        Example:
            tags = [
                {"key": "environment", "value": "production"},
                {"key": "owner", "value": "database-team"}
            ]

        Returns:
            Dictionary containing the created tags
        """
        try:
            tag_request = {"tags": tags}
            result = await client.make_request(
                "POST", f"/dsources/{dsource_id}/tags", json=tag_request
            )
            logger.info(f"Created {len(tags)} tags for dSource {dsource_id}")
            return result

        except Exception as e:
            logger.error(f"Error creating tags for dSource {dsource_id}: {str(e)}")
            raise

    @app.tool()
    async def dct_dsources_tags_delete(
        dsource_id: str, delete_parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Delete tags from a dSource.

        Args:
            dsource_id: The ID of the dSource
            delete_parameters: Parameters for tag deletion

        Returns:
            Dictionary containing the deletion result
        """
        try:
            if delete_parameters is None:
                delete_parameters = {}

            result = await client.make_request(
                "POST", f"/dsources/{dsource_id}/tags/delete", json=delete_parameters
            )
            logger.info(f"Deleted tags for dSource {dsource_id}")
            return result

        except Exception as e:
            logger.error(f"Error deleting tags for dSource {dsource_id}: {str(e)}")
            raise

    logger.info("DSources tools registered successfully")
