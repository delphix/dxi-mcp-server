"""
Shared schema reference for DCT API tools

This tool exposes concise, field-level schema summaries for core DCT objects.
Include this single tool alongside all others so the LLM has one canonical
place to reference object shapes without repeating in every tool.

Objects covered:
- VDB
- DSource
- Snapshot
- Bookmark
- Environment
- RegisteredEngine
- Job (async operation result)
- TagsResponse and Tag
- PaginatedResponseMetadata
- Errors and Error

Provisioning guidance (parent relationships and chaining):
- To CREATE a VDB, prefer point-in-time inputs over raw parent fields:
  - From snapshot: provide snapshot_id to provision endpoints.
  - From timestamp: provide source_data_id (dataset id of a VDB or dSource),
    and optionally timeflow_id or timestamp variant per endpoint.
  - From bookmark: provide bookmark_id. The bookmark encapsulates one or more
    datasets and exact data points.
- Parent fields on VDBs help navigation, not inputs:
  - parent_id: The immediate parent dataset (VDB parent or dSource), useful
    to traverse lineage when chaining operations.
  - parent_dsource_id: Present when the immediate parent is a dSource; helps
    decide when to query dSource snapshots vs VDB snapshots.
  - root_parent_id: The ultimate ancestor dataset. Use for grouping/lineage
    analysis; provisioning still uses snapshot_id/timeflow_id/bookmark_id.
"""

from typing import Any, Dict

from mcp.server.fastmcp import FastMCP
from typing import List, Optional


SCHEMAS = {
    "VDB": {
        "id": "The VDB object entity ID (e.g., 'vdb-123').",
        "name": "Logical name of the VDB.",
        "database_type": "Database type (e.g., Oracle, MSSQL, Postgres).",
        "database_name": "Name in the target system.",
        "engine_id": "Engine this VDB belongs to.",
        "engine_name": "Engine name.",
        "environment_id": "Host environment reference.",
        "status": "Runtime status (e.g., RUNNING, STOPPED, Unknown).",
        "size": "Logical size (bytes).",
        "storage_size": "Actual space used (bytes).",
        "masked": "Whether the VDB contains masked data.",
        "content_type": "Content type (e.g., PDB, etc.).",
        "namespace_id": "Namespace id.",
        "namespace_name": "Namespace name.",
        "group_name": "Group containing this VDB.",
        "cdb_id": "Reference to CDB/VCDB if applicable.",
        "parent_id": "Immediate parent dataset (VDB or dSource).",
        "parent_dsource_id": "Immediate parent when it's a dSource.",
        "root_parent_id": "Ultimate ancestor dataset (lineage).",
        "current_timeflow_id": "Active timeflow id.",
        "previous_timeflow_id": "Previous timeflow id.",
        "last_refreshed_date": "When the VDB was last refreshed.",
        "parent_timeflow_timestamp": "Parent timeflow timestamp.",
        "parent_timeflow_timezone": "Parent timeflow timezone.",
        "fqdn": "Host FQDN.",
        "ip_address": "Host IP address.",
        "tags": "Array of tags.",
        "creation_date": "When the VDB was created.",
        "mount_point": "Mount point (where applicable).",
    },
    "DSource": {
        "id": "dSource object entity ID.",
        "name": "Container name of the dSource.",
        "database_type": "Source DB type.",
        "database_version": "Source DB version.",
        "content_type": "Source content type.",
        "engine_id": "Engine hosting this dSource.",
        "engine_name": "Engine name.",
        "source_id": "Associated source identifier.",
        "staging_source_id": "Associated staging identifier.",
        "status": "Runtime status (Unknown if unreachable).",
        "namespace_id": "Namespace id.",
        "namespace_name": "Namespace name.",
        "group_name": "Group containing this dSource.",
        "data_uuid": "Universal ID of the dSource database.",
        "storage_size": "Space used (bytes).",
        "creation_date": "When created.",
        "enabled": "Whether enabled.",
        "is_detached": "Whether detached.",
        "is_appdata": "Whether AppData.",
        "current_timeflow_id": "Active timeflow.",
        "previous_timeflow_id": "Previous timeflow.",
        "cdb_id": "CDB reference (Oracle).",
        "tags": "Array of tags.",
    },
    "Snapshot": {
        "id": "Snapshot ID (e.g., 'snapshot-123').",
        "dataset_id": "ID of associated dSource or VDB.",
        "engine_id": "Engine id.",
        "name": "Snapshot name.",
        "creation_time": "When snapshot was taken.",
        "timestamp": "Logical time of the data.",
        "location": "DB-specific identifier (SCN/LSN).",
        "start_timestamp": "When capture began (logical).",
        "start_location": "When capture began (DB-specific).",
        "consistency": "CONSISTENT/INCONSISTENT/CRASH_CONSISTENT/PLUGGABLE.",
        "missing_non_logged_data": "If nologging changes would be missing.",
        "timezone": "Source DB timezone.",
        "version": "Source DB version.",
        "expiration": "Expiration date.",
        "retain_forever": "Keep forever flag.",
        "effective_expiration": "Effective expiration (with bookmarks).",
        "effective_retain_forever": "Effective retain_forever (with bookmarks).",
        "tags": "Array of tags.",
    },
    "Bookmark": {
        "id": "Bookmark ID.",
        "name": "Bookmark name.",
        "creation_date": "When bookmark was created.",
        "data_timestamp": "Data timestamp referenced.",
        "timeflow_id": "Timeflow referenced.",
        "location": "Location referenced.",
        "vdb_ids": "Included VDB IDs.",
        "dsource_ids": "Included dSource IDs.",
        "vdb_group_id": "VDB group ID.",
        "vdb_group_name": "VDB group name.",
        "vdbs": "Array of { vdb_id, vdb_name, root_parent_id, snapshot_id, timeflow_id, data_timestamp }.",
        "dsources": "Array of { dsource_id, dsource_name, snapshot_id, timeflow_id, data_timestamp }.",
        "retention": "Retention days (deprecated).",
        "expiration": "Expiration date.",
        "bookmark_source": "DCT or ENGINE.",
        "bookmark_status": "ACTIVE or INACTIVE (engine bookmarks).",
        "ss_data_layout_id": "Self-service data layout id.",
        "ss_bookmark_reference": "Self-service bookmark reference.",
        "ss_bookmark_errors": "Array of self-service errors.",
        "bookmark_type": "PUBLIC or PRIVATE.",
        "tags": "Array of tags.",
    },
    "Environment": {
        "id": "Environment ID.",
        "name": "Environment name.",
        "description": "Environment description.",
        "os_type": "UNIX or WINDOWS.",
        "engine_id": "Engine id.",
        "namespace_id": "Namespace id.",
        "namespace_name": "Namespace name.",
        "namespace": "Namespace (replicated/restored).",
        "enabled": "Whether enabled.",
        "encryption_enabled": "Whether encrypted transfer.",
        "is_cluster": "Whether cluster.",
        "cluster_home": "Cluster home.",
        "cluster_name": "Cluster name.",
        "scan": "Oracle SCAN.",
        "remote_listener": "Default remote_listener.",
        "is_windows_target": "Windows target flag.",
        "staging_environment": "Connector environment id.",
        "hosts": "Array of Host.",
        "repositories": "Array of Repository.",
        "listeners": "Array of OracleListener.",
        "env_users": "Array of EnvironmentUser.",
        "tags": "Array of tags.",
    },
    "RegisteredEngine": {
        "id": "Engine object entity ID.",
        "uuid": "Unique engine identifier.",
        "type": "Engine type.",
        "name": "Engine name.",
        "hostname": "Engine hostname.",
        "version": "Engine version.",
        "cpu_core_count": "CPU cores.",
        "memory_size": "Memory size.",
        "data_storage_capacity": "Data storage capacity.",
        "data_storage_used": "Data storage used.",
        "insecure_ssl": "Insecure SSL flag.",
        "unsafe_ssl_hostname_check": "Unsafe SSL hostname check flag.",
        "status": "Registration/status.",
        "username": "Registered username.",
        "connection_status": "Connection status.",
        "engine_connection_status": "Engine-side connection status.",
        "tags": "Array of tags.",
    },
    "Job": {
        "id": "Job ID (e.g., 'job-123').",
        "status": "PENDING/STARTED/RUNNING/WAITING/COMPLETED/FAILED/etc.",
        "type": "Internal job type identifier (stable for automation).",
        "localized_type": "Human-friendly localized type label.",
        "target_id": "Target object id.",
        "target_name": "Target object name.",
        "start_time": "When job started.",
        "update_time": "When job last updated.",
        "is_waiting_for_telemetry": "Operations completed but object changes not yet reflected; occurs only while STARTED and won't transition to FAILED.",
        "error_details": "Failure details for FAILED jobs.",
        "warning_message": "Warning details.",
        "percent_complete": "Completion percentage.",
        "tasks": "Array of JobTask",
        "result_type": "Type of the result payload (if any).",
        "result": "Result payload (if any).",
    },
    "TagsResponse": {
        "tags": "Array of Tag { key, value }.",
    },
    "PaginatedResponseMetadata": {
        "prev_cursor": "Pointer to previous page.",
        "next_cursor": "Pointer to next page.",
        "total": "Total number of results (optional).",
    },
    "Errors": {
        "errors": "Array of Error { message, object_name }.",
    },
}


def register_schema_docs(mcp: FastMCP) -> None:
    """Register a single shared schema reference tool for all categories.

    The tool's description contains the schema summaries so the LLM always
    receives them once per session when tools are provided.
    """

    @mcp.tool()
    async def describe_schema(object: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Describe schema for a DCT object

        Args:
            object: One of VDB, DSource, Snapshot, Bookmark, Environment, RegisteredEngine, Job, TagsResponse, PaginatedResponseMetadata, Errors
            fields: Optional list of field names to filter; if omitted, returns all fields

        """

        obj = object.strip()
        if obj not in SCHEMAS:
            return {"error": f"Unknown object '{object}'. Valid: {', '.join(sorted(SCHEMAS.keys()))}"}

        schema = SCHEMAS[obj]
        if fields:
            filtered = {k: v for k, v in schema.items() if k in fields}
            missing = [f for f in fields if f not in schema]
            return {"object": obj, "fields": filtered, "missing": missing}
        return {"object": obj, "fields": schema}

    @mcp.tool()
    async def explain_field(object: str, field: str) -> Dict[str, Any]:
        """Explain a single field in a DCT object schema

        Args:
            object: One of the supported schema objects
            field: Field name to explain
        """
        obj = object.strip()
        if obj not in SCHEMAS:
            return {"error": f"Unknown object '{object}'. Valid: {', '.join(sorted(SCHEMAS.keys()))}"}
        schema = SCHEMAS[obj]
        if field not in schema:
            return {"object": obj, "missing": [field]}
        return {"object": obj, "field": field, "description": schema[field]}

    @mcp.tool()
    async def provisioning_guidance() -> Dict[str, Any]:
        """Guidance on choosing identifiers for provisioning and refresh/rollback

        Returns recommended identifiers and how parent/root fields are used.
        """
        return {
            "provision_from_snapshot": "Use snapshot_id with provision_by_snapshot.",
            "provision_from_timestamp": "Use source_data_id (dataset id of a VDB or dSource) and timeflow/timestamp inputs with provision_by_timestamp.",
            "provision_from_bookmark": "Use bookmark_id with provision_from_bookmark.",
            "parent_id": "Immediate lineage traversal (choose dSource vs VDB path).",
            "parent_dsource_id": "Indicates immediate parent is a dSource (search dSource snapshots).",
            "root_parent_id": "Ultimate ancestor for lineage analytics; not passed to provision endpoints.",
        }

    @mcp.tool()
    async def job_guidance() -> Dict[str, Any]:
        """Explain job lifecycle and terminal statuses.

        Useful for deciding when to stop polling and how to interpret results.
        """
        return {
            "terminal_statuses": [
                "COMPLETED",
                "FAILED",
                "CANCELED",
                "ABANDONED",
                "TIMEDOUT",
            ],
            "non_terminal_examples": [
                "PENDING",
                "STARTED",
                "RUNNING",
                "WAITING",
                "SUSPENDED",
            ],
            "notes": "While STARTED, is_waiting_for_telemetry may be true indicating operations finished but object state not yet reflected.",
        }


