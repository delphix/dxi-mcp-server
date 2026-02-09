from mcp.server.fastmcp import FastMCP
from typing import Dict,Any,Optional
from dct_mcp_server.core.decorators import log_tool_execution
import asyncio
import logging
import threading
from functools import wraps

client = None
logger = logging.getLogger(__name__)

def async_to_sync(async_func):
    """Utility decorator to convert async functions to sync with proper event loop handling."""
    @wraps(async_func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a task and run it synchronously
                result = None
                exception = None
                def run_in_thread():
                    nonlocal result, exception
                    try:
                        result = asyncio.run(async_func(*args, **kwargs))
                    except Exception as e:
                        exception = e
                thread = threading.Thread(target=run_in_thread)
                thread.start()
                thread.join()
                if exception:
                    raise exception
                return result
            else:
                return loop.run_until_complete(async_func(*args, **kwargs))
        except RuntimeError:
            return asyncio.run(async_func(*args, **kwargs))
    return wrapper

def make_api_request(method: str, endpoint: str, params: dict = None, json_body: dict = None):
    """Utility function to make API requests with consistent parameter handling."""
    @async_to_sync
    async def _make_request():
        return await client.make_request(method, endpoint, params=params or {}, json=json_body)
    return _make_request()

def build_params(**kwargs):
    """Build parameters dictionary excluding None values."""
    return {k: v for k, v in kwargs.items() if v is not None}

@log_tool_execution
def search_bookmarks(limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None, filter_expression: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for bookmarks.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.(optional)
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.(optional)
    :param sort: The field to sort results by. A property name with a prepended '-' signifies descending order.
    :param sort: The field to sort results by. A property name with a prepended '-' signifies descending order.(optional)
    :param filter_expression: Filter expression string (optional)
    Filter expression can include the following fields:
     - id: The Bookmark object entity ID.
     - name: The user-defined name of this bookmark.
     - creation_date: The date and time that this bookmark was created.
     - data_timestamp: The timestamp for the data that the bookmark refers to.
     - timeflow_id: The timeflow for the snapshot that the bookmark was created of.
     - location: The location for the data that the bookmark refers to.
     - vdb_ids: The list of VDB IDs associated with this bookmark.
     - dsource_ids: The list of dSource IDs associated with this bookmark.
     - vdb_group_id: The ID of the VDB group on which bookmark is created.
     - vdb_group_name: The name of the VDB group on which bookmark is created.
     - vdbs: The list of VDB IDs and VDB names associated with this bookmark.
     - dsources: The list of dSource IDs and dSource names associated with this bookmark.
     - retention: The retention policy for this bookmark, in days. A value of -1 indicates the bookmark should be kept forever. Deprecated in favor of expiration.
     - expiration: The expiration for this bookmark. When unset, indicates the bookmark is kept forever except for bookmarks of replicated datasets. Expiration cannot be set for bookmarks of replicated datasets.
     - status: A message with details about operation progress or state of this bookmark.
     - replicated_dataset: Whether this bookmark is created from a replicated dataset or not.
     - bookmark_source: Source of the bookmark, default is DCT. In case of self-service bookmarks, this value would be ENGINE.
     - bookmark_status: Status of the bookmark. It can have INACTIVE value for engine bookmarks only. If this value is INACTIVE then ss_bookmark_errors would have the list of associated errors.
     - ss_data_layout_id: Data-layout Id for engine-managed bookmarks.
     - ss_bookmark_reference: Engine reference of the self-service bookmark.
     - ss_bookmark_errors: List of errors if any, during bookmark creation in DCT from self-service.
     - bookmark_type: Type of the bookmark, either PUBLIC or PRIVATE.
     - namespace_id: The namespace id of this bookmark.
     - namespace_name: The namespace name of this bookmark.
     - is_replica: Is this a replicated bookmark.
     - primary_object_id: Id of the parent bookmark from which this bookmark was replicated.
     - primary_engine_id: The ID of the parent engine from which replication was done.
     - primary_engine_name: The name of the parent engine from which replication was done.
     - replicas: The list of replicas replicated from this object.
     - tags: The tags to be created for this Bookmark.

    How to use filter_expresssion: 
    A request body containing a filter expression. This enables searching
    for items matching arbitrarily complex conditions. The list of
    attributes which can be used in filter expressions is available
    in the x-filterable vendor extension.
    
    # Filter Expression Overview
    **Note: All keywords are case-insensitive**
    
    ## Comparison Operators
    | Operator | Description | Example |
    | --- | --- | --- |
    | CONTAINS | Substring or membership testing for string and list attributes respectively. | field3 CONTAINS 'foobar', field4 CONTAINS TRUE  |
    | IN | Tests if field is a member of a list literal. List can contain a maximum of 100 values | field2 IN ['Goku', 'Vegeta'] |
    | GE | Tests if a field is greater than or equal to a literal value | field1 GE 1.2e-2 |
    | GT | Tests if a field is greater than a literal value | field1 GT 1.2e-2 |
    | LE | Tests if a field is less than or equal to a literal value | field1 LE 9000 |
    | LT | Tests if a field is less than a literal value | field1 LT 9.02 |
    | NE | Tests if a field is not equal to a literal value | field1 NE 42 |
    | EQ | Tests if a field is equal to a literal value | field1 EQ 42 |
    
    ## Search Operator
    The SEARCH operator filters for items which have any filterable
    attribute that contains the input string as a substring, comparison
    is done case-insensitively. This is not restricted to attributes with
    string values. Specifically `SEARCH '12'` would match an item with an
    attribute with an integer value of `123`.
    
    ## Logical Operators
    Ordered by precedence.
    | Operator | Description | Example |
    | --- | --- | --- |
    | NOT | Logical NOT (Right associative) | NOT field1 LE 9000 |
    | AND | Logical AND (Left Associative) | field1 GT 9000 AND field2 EQ 'Goku' |
    | OR | Logical OR (Left Associative) | field1 GT 9000 OR field2 EQ 'Goku' |
    
    ## Grouping
    Parenthesis `()` can be used to override operator precedence.
    
    For example:
    NOT (field1 LT 1234 AND field2 CONTAINS 'foo')
    
    ## Literal Values
    | Literal      | Description | Examples |
    | --- | --- | --- |
    | Nil | Represents the absence of a value | nil, Nil, nIl, NIL |
    | Boolean | true/false boolean | true, false, True, False, TRUE, FALSE |
    | Number | Signed integer and floating point numbers. Also supports scientific notation. | 0, 1, -1, 1.2, 0.35, 1.2e-2, -1.2e+2 |
    | String | Single or double quoted | "foo", "bar", "foo bar", 'foo', 'bar', 'foo bar' |
    | Datetime | Formatted according to [RFC3339](https://datatracker.ietf.org/doc/html/rfc3339) | 2018-04-27T18:39:26.397237+00:00 |
    | List | Comma-separated literals wrapped in square brackets | [0], [0, 1], ['foo', "bar"] |
    
    ## Limitations
    - A maximum of 8 unique identifiers may be used inside a filter expression.
    
    """
    # Build parameters excluding None values
    params = build_params(limit=limit, cursor=cursor, sort=sort)
    search_body = {'filter_expression': filter_expression}
    return make_api_request('POST', '/bookmarks/search', params=params, json_body=search_body)

@log_tool_execution
def search_data_connections(limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None, filter_expression: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for data connections.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.(optional)
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.(optional)
    :param sort: The field to sort results by. A property name with a prepended '-' signifies descending order.
    :param sort: The field to sort results by. A property name with a prepended '-' signifies descending order.(optional)
    :param filter_expression: Filter expression string (optional)
    Filter expression can include the following fields:
     - id: ID of the data connection.
     - name: Name of the data connection.
     - status: ACTIVE if used by a masking job or a linked dSource or VDB.
     - type: The type of the data connection.
     - platform: The dataset platform of the data connection.
     - dsource_count: The number of dSources linked from this data connection.
     - capabilities: Types of functionality supported by this data connection.
     - tags: The tags associated with this data connection.
     - hostname: The combined port and hostname or IP address of the data connection.
     - database_name: The database name.
     - custom_driver_name: The name of the custom JDBC driver.
     - path: The path to the FILE data on the remote host.
     - size: The size of the data connection in bytes. This is equivalent of the disk space, in bytes, that it would take to store the dSource and its descendant VDBs without Delphix, counting each of their timeflows as separate copy of the parent source data.

    How to use filter_expresssion: 
    A request body containing a filter expression. This enables searching
    for items matching arbitrarily complex conditions. The list of
    attributes which can be used in filter expressions is available
    in the x-filterable vendor extension.
    
    # Filter Expression Overview
    **Note: All keywords are case-insensitive**
    
    ## Comparison Operators
    | Operator | Description | Example |
    | --- | --- | --- |
    | CONTAINS | Substring or membership testing for string and list attributes respectively. | field3 CONTAINS 'foobar', field4 CONTAINS TRUE  |
    | IN | Tests if field is a member of a list literal. List can contain a maximum of 100 values | field2 IN ['Goku', 'Vegeta'] |
    | GE | Tests if a field is greater than or equal to a literal value | field1 GE 1.2e-2 |
    | GT | Tests if a field is greater than a literal value | field1 GT 1.2e-2 |
    | LE | Tests if a field is less than or equal to a literal value | field1 LE 9000 |
    | LT | Tests if a field is less than a literal value | field1 LT 9.02 |
    | NE | Tests if a field is not equal to a literal value | field1 NE 42 |
    | EQ | Tests if a field is equal to a literal value | field1 EQ 42 |
    
    ## Search Operator
    The SEARCH operator filters for items which have any filterable
    attribute that contains the input string as a substring, comparison
    is done case-insensitively. This is not restricted to attributes with
    string values. Specifically `SEARCH '12'` would match an item with an
    attribute with an integer value of `123`.
    
    ## Logical Operators
    Ordered by precedence.
    | Operator | Description | Example |
    | --- | --- | --- |
    | NOT | Logical NOT (Right associative) | NOT field1 LE 9000 |
    | AND | Logical AND (Left Associative) | field1 GT 9000 AND field2 EQ 'Goku' |
    | OR | Logical OR (Left Associative) | field1 GT 9000 OR field2 EQ 'Goku' |
    
    ## Grouping
    Parenthesis `()` can be used to override operator precedence.
    
    For example:
    NOT (field1 LT 1234 AND field2 CONTAINS 'foo')
    
    ## Literal Values
    | Literal      | Description | Examples |
    | --- | --- | --- |
    | Nil | Represents the absence of a value | nil, Nil, nIl, NIL |
    | Boolean | true/false boolean | true, false, True, False, TRUE, FALSE |
    | Number | Signed integer and floating point numbers. Also supports scientific notation. | 0, 1, -1, 1.2, 0.35, 1.2e-2, -1.2e+2 |
    | String | Single or double quoted | "foo", "bar", "foo bar", 'foo', 'bar', 'foo bar' |
    | Datetime | Formatted according to [RFC3339](https://datatracker.ietf.org/doc/html/rfc3339) | 2018-04-27T18:39:26.397237+00:00 |
    | List | Comma-separated literals wrapped in square brackets | [0], [0, 1], ['foo', "bar"] |
    
    ## Limitations
    - A maximum of 8 unique identifiers may be used inside a filter expression.
    
    """
    # Build parameters excluding None values
    params = build_params(limit=limit, cursor=cursor, sort=sort)
    search_body = {'filter_expression': filter_expression}
    return make_api_request('POST', '/data-connections/search', params=params, json_body=search_body)

@log_tool_execution
def search_dsources(limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None, filter_expression: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for dSources.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.(optional)
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.(optional)
    :param sort: The field to sort results by. A property name with a prepended '-' signifies descending order.
    :param sort: The field to sort results by. A property name with a prepended '-' signifies descending order.(optional)
    :param filter_expression: Filter expression string (optional)
    Filter expression can include the following fields:
     - id: The dSource object entity ID.
     - database_type: The database type of this dSource.
     - name: The container name of this dSource.
     - description: The container description of this dSource.
     - namespace_id: The namespace id of this dSource.
     - namespace_name: The namespace name of this dSource.
     - is_replica: Is this a replicated object.
     - database_version: The database version of this dSource.
     - content_type: The content type of the dSource.
     - data_uuid: A universal ID that uniquely identifies the dSource database.
     - storage_size: The actual space used by this dSource, in bytes.
     - plugin_version: The version of the plugin associated with this source database.
     - creation_date: The date this dSource was created.
     - group_name: The name of the group containing this dSource.
     - enabled: A value indicating whether this dSource is enabled.
     - is_detached: A value indicating whether this dSource is detached.
     - engine_id: A reference to the Engine that this dSource belongs to.
     - source_id: A reference to the Source associated with this dSource.
     - staging_source_id: A reference to the Staging Source associated with this dSource.
     - status: The runtime status of the dSource. 'Unknown' if all attempts to connect to the source failed.
     - engine_name: Name of the Engine where this DSource is hosted
     - cdb_id: A reference to the CDB associated with this dSource.
     - current_timeflow_id: A reference to the currently active timeflow for this dSource.
     - previous_timeflow_id: A reference to the previous timeflow for this dSource.
     - is_appdata: Indicates whether this dSource has an AppData database.
     - toolkit_id: The ID of the toolkit associated with this dSource(AppData only).
     - unvirtualized_space: This is the sum of unvirtualized space from the dependants VDBs of the dSource.
     - dependant_vdbs: The number of VDBs that are dependant on this dSource. This includes all VDB descendants that have this dSource as an ancestor.
     - appdata_source_params: The JSON payload conforming to the DraftV4 schema based on the type of application data being manipulated.
     - appdata_config_params: The parameters specified by the source config schema in the toolkit
     - tags: No description
     - primary_object_id: The ID of the parent object from which replication was done.
     - primary_engine_id: The ID of the parent engine from which replication was done.
     - primary_engine_name: The name of the parent engine from which replication was done.
     - replicas: The list of replicas replicated from this object.
     - hooks: No description
     - sync_policy_id: The id of the snapshot policy associated with this dSource.
     - retention_policy_id: The id of the retention policy associated with this dSource.
     - replica_retention_policy_id: The id of the replica retention policy associated with this dSource.
     - quota_policy_id: The id of the quota policy associated with this dSource.
     - logsync_enabled: True if LogSync is enabled for this dSource.
     - logsync_mode: No description
     - logsync_interval: Interval between LogSync requests, in seconds.
     - exported_data_directory: ZFS exported data directory path.
     - template_id: A reference to the Non Virtual Database Template.
     - allow_auto_staging_restart_on_host_reboot: Indicates whether Delphix should automatically restart this staging database when staging host reboot is detected.
     - physical_standby: Indicates whether this staging database is configured as a physical standby.
     - validate_by_opening_db_in_read_only_mode: Indicates whether this staging database snapshot is validated by opening it in read-only mode.
     - mssql_sync_strategy_managed_type: No description
     - validated_sync_mode: Specifies the backup types ValidatedSync will use to synchronize the dSource with the source database.
     - shared_backup_locations: Shared source database backup locations.
     - backup_policy: Specify which node of an availability group to run the copy-only full backup on
     - compression_enabled: Specify whether the backups taken should be compressed or uncompressed.
     - staging_database_name: The name of the staging database
     - db_state: User provided db state that is used to create staging push db
     - encryption_key: The encryption key to use when restoring encrypted backups.
     - external_netbackup_config_master_name: The master server name of this NetBackup configuration.
     - external_netbackup_config_source_client_name: The source's client server name of this NetBackup configuration.
     - external_netbackup_config_params: NetBackup configuration parameter overrides.
     - external_netbackup_config_templates: Optional config template selection for NetBackup configurations.
     - external_commserve_host_name: The commserve host name of this Commvault configuration.
     - external_commvault_config_source_client_name: The source client name of this Commvault configuration.
     - external_commvault_config_staging_client_name: The staging client name of this Commvault configuration.
     - external_commvault_config_params: Commvault configuration parameter overrides.
     - external_commvault_config_templates: Optional config template selection for Commvault configurations.
     - mssql_user_type: Database user type for Database authentication.
     - domain_user_credential_type: credential types.
     - mssql_database_username: The database user name for database user type.
     - mssql_user_environment_reference: The name or reference of the environment user for environment user type.
     - mssql_user_domain_username: Domain User name for password credentials.
     - mssql_user_domain_vault_username: Delphix display name for the vault user.
     - mssql_user_domain_vault: The name or reference of the vault.
     - mssql_user_domain_hashicorp_vault_engine: Vault engine name where the credential is stored.
     - mssql_user_domain_hashicorp_vault_secret_path: Path in the vault engine where the credential is stored.
     - mssql_user_domain_hashicorp_vault_username_key: Hashicorp vault key for the username in the key-value store.
     - mssql_user_domain_hashicorp_vault_secret_key: Hashicorp vault key for the password in the key-value store.
     - mssql_user_domain_azure_vault_name: Azure key vault name.
     - mssql_user_domain_azure_vault_username_key: Azure vault key in the key-value store.
     - mssql_user_domain_azure_vault_secret_key: Azure vault key in the key-value store.
     - mssql_user_domain_cyberark_vault_query_string: Query to find a credential in the CyberArk vault.
     - diagnose_no_logging_faults: If true, NOLOGGING operations on this container are treated as faults and cannot be resolved manually. Otherwise, these operations are ignored.
     - pre_provisioning_enabled: If true, pre-provisioning will be performed after every sync.
     - backup_level_enabled: Boolean value indicates whether LEVEL-based incremental backups can be used on the source db.
     - rman_channels: Number of parallel channels to use.
     - files_per_set: Number of data files to include in each RMAN backup set.
     - check_logical: True if extended block checking should be used for this linked database.
     - encrypted_linking_enabled: True if SnapSync data from the source should be retrieved through an encrypted connection. Enabling this feature can decrease the performance of SnapSync from the source but has no impact on the performance of VDBs created from the retrieved data.
     - compressed_linking_enabled: True if SnapSync data from the source should be compressed over the network. Enabling this feature will reduce network bandwidth consumption and may significantly improve throughput, especially over slow network.
     - bandwidth_limit: Bandwidth limit (MB/s) for SnapSync and LogSync network traffic. A value of 0 means no limit.
     - number_of_connections: Total number of transport connections to use during SnapSync.
     - data_connection_id: The ID of the associated DataConnection.

    How to use filter_expresssion: 
    A request body containing a filter expression. This enables searching
    for items matching arbitrarily complex conditions. The list of
    attributes which can be used in filter expressions is available
    in the x-filterable vendor extension.
    
    # Filter Expression Overview
    **Note: All keywords are case-insensitive**
    
    ## Comparison Operators
    | Operator | Description | Example |
    | --- | --- | --- |
    | CONTAINS | Substring or membership testing for string and list attributes respectively. | field3 CONTAINS 'foobar', field4 CONTAINS TRUE  |
    | IN | Tests if field is a member of a list literal. List can contain a maximum of 100 values | field2 IN ['Goku', 'Vegeta'] |
    | GE | Tests if a field is greater than or equal to a literal value | field1 GE 1.2e-2 |
    | GT | Tests if a field is greater than a literal value | field1 GT 1.2e-2 |
    | LE | Tests if a field is less than or equal to a literal value | field1 LE 9000 |
    | LT | Tests if a field is less than a literal value | field1 LT 9.02 |
    | NE | Tests if a field is not equal to a literal value | field1 NE 42 |
    | EQ | Tests if a field is equal to a literal value | field1 EQ 42 |
    
    ## Search Operator
    The SEARCH operator filters for items which have any filterable
    attribute that contains the input string as a substring, comparison
    is done case-insensitively. This is not restricted to attributes with
    string values. Specifically `SEARCH '12'` would match an item with an
    attribute with an integer value of `123`.
    
    ## Logical Operators
    Ordered by precedence.
    | Operator | Description | Example |
    | --- | --- | --- |
    | NOT | Logical NOT (Right associative) | NOT field1 LE 9000 |
    | AND | Logical AND (Left Associative) | field1 GT 9000 AND field2 EQ 'Goku' |
    | OR | Logical OR (Left Associative) | field1 GT 9000 OR field2 EQ 'Goku' |
    
    ## Grouping
    Parenthesis `()` can be used to override operator precedence.
    
    For example:
    NOT (field1 LT 1234 AND field2 CONTAINS 'foo')
    
    ## Literal Values
    | Literal      | Description | Examples |
    | --- | --- | --- |
    | Nil | Represents the absence of a value | nil, Nil, nIl, NIL |
    | Boolean | true/false boolean | true, false, True, False, TRUE, FALSE |
    | Number | Signed integer and floating point numbers. Also supports scientific notation. | 0, 1, -1, 1.2, 0.35, 1.2e-2, -1.2e+2 |
    | String | Single or double quoted | "foo", "bar", "foo bar", 'foo', 'bar', 'foo bar' |
    | Datetime | Formatted according to [RFC3339](https://datatracker.ietf.org/doc/html/rfc3339) | 2018-04-27T18:39:26.397237+00:00 |
    | List | Comma-separated literals wrapped in square brackets | [0], [0, 1], ['foo', "bar"] |
    
    ## Limitations
    - A maximum of 8 unique identifiers may be used inside a filter expression.
    
    """
    # Build parameters excluding None values
    params = build_params(limit=limit, cursor=cursor, sort=sort)
    search_body = {'filter_expression': filter_expression}
    return make_api_request('POST', '/dsources/search', params=params, json_body=search_body)

@log_tool_execution
def search_snapshots(limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None, filter_expression: Optional[str] = None) -> Dict[str, Any]:
    """
    Search snapshots.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.(optional)
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.(optional)
    :param sort: The field to sort results by. A property name with a prepended '-' signifies descending order.
    :param sort: The field to sort results by. A property name with a prepended '-' signifies descending order.(optional)
    :param filter_expression: Filter expression string (optional)
    Filter expression can include the following fields:
     - id: The Snapshot ID.
     - engine_id: The id of the engine the snapshot belongs to.
     - namespace: Alternate namespace for this object, for replicated and restored snapshots.
     - name: The snapshot's name.
     - namespace_id: The namespace id of this snapshot.
     - namespace_name: The namespace name of this snapshot.
     - is_replica: Is this a replicated object.
     - consistency: Indicates what type of recovery strategies must be invoked when provisioning from this snapshot.
     - missing_non_logged_data: Indicates if a virtual database provisioned from this snapshot will be missing nologging changes.
     - dataset_id: The ID of the Snapshot's dSource or VDB.
     - creation_time: The time when the snapshot was created.
     - start_timestamp: The timestamp within the parent TimeFlow at which this snapshot was initiated. \
No recovery earlier than this point needs to be applied in order to provision a database from \
this snapshot. If start_timestamp equals timestamp, then no recovery needs to be \
applied in order to provision a database.

     - start_location: The database specific indentifier within the parent TimeFlow at which this snapshot was initiated. \
No recovery earlier than this point needs to be applied in order to provision a database from \
this snapshot. If start_location equals location, then no recovery needs to be \
applied in order to provision a database.

     - timestamp: The logical time of the data contained in this Snapshot.
     - location: Database specific identifier for the data contained in this Snapshot, such as the Log Sequence Number (LSN) for MSsql databases, System Change Number (SCN) for Oracle databases.
     - retention: Retention policy, in days. A value of -1 indicates the snapshot should be kept forever. Deprecated in favor of expiration and retain_forever.
     - expiration: The expiration date of this snapshot. If this is unset and retain_forever is false, and the snapshot is not included in a Bookmark, the snapshot is subject to the retention policy of its dataset.
     - retain_forever: Indicates that the snapshot is protected from retention, i.e it will be kept forever. If false, see expiration.
     - effective_expiration: The effective expiration is that max of the snapshot expiration and the expiration of any Bookmark which includes this snapshot.
     - effective_retain_forever: True if retain_forever is set or a Bookmark retains this snapshot forever.
     - timeflow_id: The TimeFlow this snapshot was taken on.
     - timezone: Time zone of the source database at the time the snapshot was taken.
     - version: Version of database source repository at the time the snapshot was taken.
     - temporary: Indicates that this snapshot is in a transient state and should not be user visible.
     - appdata_toolkit: The toolkit associated with this snapshot.
     - appdata_metadata: The JSON payload conforming to the DraftV4 schema based on the type of application data being manipulated.
     - ase_db_encryption_key: Database encryption key present for this snapshot.
     - mssql_internal_version: Internal version of the source database at the time the snapshot was taken.
     - mssql_backup_set_uuid: UUID of the source database backup that was restored for this snapshot.
     - mssql_backup_software_type: Backup software used to restore the source database backup for this snapshot
     - mssql_backup_location_type: Backup software used to restore the source database backup for this snapshot
     - mssql_empty_snapshot: True if the staging push dSource snapshot is empty.
     - oracle_from_physical_standby_vdb: True if this snapshot was taken of a standby database.
     - oracle_redo_log_size_in_bytes: Online redo log size in bytes when this snapshot was taken.
     - tags: No description

    How to use filter_expresssion: 
    A request body containing a filter expression. This enables searching
    for items matching arbitrarily complex conditions. The list of
    attributes which can be used in filter expressions is available
    in the x-filterable vendor extension.
    
    # Filter Expression Overview
    **Note: All keywords are case-insensitive**
    
    ## Comparison Operators
    | Operator | Description | Example |
    | --- | --- | --- |
    | CONTAINS | Substring or membership testing for string and list attributes respectively. | field3 CONTAINS 'foobar', field4 CONTAINS TRUE  |
    | IN | Tests if field is a member of a list literal. List can contain a maximum of 100 values | field2 IN ['Goku', 'Vegeta'] |
    | GE | Tests if a field is greater than or equal to a literal value | field1 GE 1.2e-2 |
    | GT | Tests if a field is greater than a literal value | field1 GT 1.2e-2 |
    | LE | Tests if a field is less than or equal to a literal value | field1 LE 9000 |
    | LT | Tests if a field is less than a literal value | field1 LT 9.02 |
    | NE | Tests if a field is not equal to a literal value | field1 NE 42 |
    | EQ | Tests if a field is equal to a literal value | field1 EQ 42 |
    
    ## Search Operator
    The SEARCH operator filters for items which have any filterable
    attribute that contains the input string as a substring, comparison
    is done case-insensitively. This is not restricted to attributes with
    string values. Specifically `SEARCH '12'` would match an item with an
    attribute with an integer value of `123`.
    
    ## Logical Operators
    Ordered by precedence.
    | Operator | Description | Example |
    | --- | --- | --- |
    | NOT | Logical NOT (Right associative) | NOT field1 LE 9000 |
    | AND | Logical AND (Left Associative) | field1 GT 9000 AND field2 EQ 'Goku' |
    | OR | Logical OR (Left Associative) | field1 GT 9000 OR field2 EQ 'Goku' |
    
    ## Grouping
    Parenthesis `()` can be used to override operator precedence.
    
    For example:
    NOT (field1 LT 1234 AND field2 CONTAINS 'foo')
    
    ## Literal Values
    | Literal      | Description | Examples |
    | --- | --- | --- |
    | Nil | Represents the absence of a value | nil, Nil, nIl, NIL |
    | Boolean | true/false boolean | true, false, True, False, TRUE, FALSE |
    | Number | Signed integer and floating point numbers. Also supports scientific notation. | 0, 1, -1, 1.2, 0.35, 1.2e-2, -1.2e+2 |
    | String | Single or double quoted | "foo", "bar", "foo bar", 'foo', 'bar', 'foo bar' |
    | Datetime | Formatted according to [RFC3339](https://datatracker.ietf.org/doc/html/rfc3339) | 2018-04-27T18:39:26.397237+00:00 |
    | List | Comma-separated literals wrapped in square brackets | [0], [0, 1], ['foo', "bar"] |
    
    ## Limitations
    - A maximum of 8 unique identifiers may be used inside a filter expression.
    
    """
    # Build parameters excluding None values
    params = build_params(limit=limit, cursor=cursor, sort=sort)
    search_body = {'filter_expression': filter_expression}
    return make_api_request('POST', '/snapshots/search', params=params, json_body=search_body)

@log_tool_execution
def search_sources(limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None, filter_expression: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for Sources.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.(optional)
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.(optional)
    :param sort: The field to sort results by. A property name with a prepended '-' signifies descending order.
    :param sort: The field to sort results by. A property name with a prepended '-' signifies descending order.(optional)
    :param filter_expression: Filter expression string (optional)
    Filter expression can include the following fields:
     - id: The Source object entity ID.
     - database_type: The type of this source database.
     - name: The name of this source database.
     - namespace_id: The namespace id of this source database.
     - namespace_name: The namespace name of this source database.
     - is_replica: Is this a replicated object.
     - database_version: The version of this source database.
     - environment_id: A reference to the Environment that hosts this source database.
     - environment_name: name of environment that hosts this source database.
     - data_uuid: A universal ID that uniquely identifies this source database.
     - ip_address: The IP address of the source's host.
     - fqdn: The FQDN of the source's host.
     - size: The total size of this source database, in bytes.
     - jdbc_connection_string: The JDBC connection URL for this source database.
     - plugin_version: The version of the plugin associated with this source database.
     - toolkit_id: The ID of the toolkit associated with this source database(AppData only).
     - is_dsource: No description
     - repository: The repository id for this source
     - recovery_model: Recovery model of the source database (MSSql Only).
     - mssql_source_type: The type of this mssql source database (MSSql Only).
     - appdata_source_type: The type of this appdata source database (Appdata Only).
     - is_pdb: If this source is of PDB type (Oracle Only).
     - tags: No description
     - instance_name: The instance name of this single instance database source.
     - instance_number: The instance number of this single instance database source.
     - instances: No description
     - oracle_services: No description
     - user: The username of the database user.
     - environment_user_ref: The environment user reference.
     - non_sys_user: The username of a database user that does not have administrative privileges.
     - discovered: Whether this source was discovered.
     - linking_enabled: Whether this source should be used for linking.
     - cdb_type: The cdb type for this source. (Oracle only)
     - data_connection_id: The ID of the associated DataConnection.
     - database_name: The name of this source database.
     - database_unique_name: The unique name of the database.

    How to use filter_expresssion: 
    A request body containing a filter expression. This enables searching
    for items matching arbitrarily complex conditions. The list of
    attributes which can be used in filter expressions is available
    in the x-filterable vendor extension.
    
    # Filter Expression Overview
    **Note: All keywords are case-insensitive**
    
    ## Comparison Operators
    | Operator | Description | Example |
    | --- | --- | --- |
    | CONTAINS | Substring or membership testing for string and list attributes respectively. | field3 CONTAINS 'foobar', field4 CONTAINS TRUE  |
    | IN | Tests if field is a member of a list literal. List can contain a maximum of 100 values | field2 IN ['Goku', 'Vegeta'] |
    | GE | Tests if a field is greater than or equal to a literal value | field1 GE 1.2e-2 |
    | GT | Tests if a field is greater than a literal value | field1 GT 1.2e-2 |
    | LE | Tests if a field is less than or equal to a literal value | field1 LE 9000 |
    | LT | Tests if a field is less than a literal value | field1 LT 9.02 |
    | NE | Tests if a field is not equal to a literal value | field1 NE 42 |
    | EQ | Tests if a field is equal to a literal value | field1 EQ 42 |
    
    ## Search Operator
    The SEARCH operator filters for items which have any filterable
    attribute that contains the input string as a substring, comparison
    is done case-insensitively. This is not restricted to attributes with
    string values. Specifically `SEARCH '12'` would match an item with an
    attribute with an integer value of `123`.
    
    ## Logical Operators
    Ordered by precedence.
    | Operator | Description | Example |
    | --- | --- | --- |
    | NOT | Logical NOT (Right associative) | NOT field1 LE 9000 |
    | AND | Logical AND (Left Associative) | field1 GT 9000 AND field2 EQ 'Goku' |
    | OR | Logical OR (Left Associative) | field1 GT 9000 OR field2 EQ 'Goku' |
    
    ## Grouping
    Parenthesis `()` can be used to override operator precedence.
    
    For example:
    NOT (field1 LT 1234 AND field2 CONTAINS 'foo')
    
    ## Literal Values
    | Literal      | Description | Examples |
    | --- | --- | --- |
    | Nil | Represents the absence of a value | nil, Nil, nIl, NIL |
    | Boolean | true/false boolean | true, false, True, False, TRUE, FALSE |
    | Number | Signed integer and floating point numbers. Also supports scientific notation. | 0, 1, -1, 1.2, 0.35, 1.2e-2, -1.2e+2 |
    | String | Single or double quoted | "foo", "bar", "foo bar", 'foo', 'bar', 'foo bar' |
    | Datetime | Formatted according to [RFC3339](https://datatracker.ietf.org/doc/html/rfc3339) | 2018-04-27T18:39:26.397237+00:00 |
    | List | Comma-separated literals wrapped in square brackets | [0], [0, 1], ['foo', "bar"] |
    
    ## Limitations
    - A maximum of 8 unique identifiers may be used inside a filter expression.
    
    """
    # Build parameters excluding None values
    params = build_params(limit=limit, cursor=cursor, sort=sort)
    search_body = {'filter_expression': filter_expression}
    return make_api_request('POST', '/sources/search', params=params, json_body=search_body)

@log_tool_execution
def search_timeflows(limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None, filter_expression: Optional[str] = None) -> Dict[str, Any]:
    """
    Search timeflows.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.(optional)
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.(optional)
    :param sort: The field to sort results by. A property name with a prepended '-' signifies descending order.
    :param sort: The field to sort results by. A property name with a prepended '-' signifies descending order.(optional)
    :param filter_expression: Filter expression string (optional)
    Filter expression can include the following fields:
     - id: The Timeflow ID.
     - engine_id: The ID of the engine the timeflow belongs to.
     - namespace: Alternate namespace for this object, for replicated and restored timeflows.
     - namespace_id: The namespace id of this timeflows.
     - namespace_name: The namespace name of this timeflows.
     - is_replica: Is this a replicated object.
     - name: The timeflow's name.
     - dataset_id: The ID of the timeflow's dSource or VDB.
     - creation_type: The source action that created the timeflow.
     - parent_snapshot_id: The ID of the timeflow's parent snapshot.
     - parent_point_location: The location on the parent timeflow from which this timeflow was provisioned. This will not be present for timeflows derived from linked sources.
     - parent_point_timestamp: The timestamp on the parent timeflow from which this timeflow was provisioned. This will not be present for timeflows derived from linked sources.
     - parent_point_timeflow_id: A reference to the parent timeflow from which this timeflow was provisioned. This will not be present for timeflows derived from linked sources.
     - parent_vdb_id: The ID of the parent VDB. This is mutually exclusive with parent_dsource_id.
     - parent_dsource_id: The ID of the parent dSource. This is mutually exclusive with parent_vdb_id.
     - source_vdb_id: The ID of the source VDB. This is mutually exclusive with source_dsource_id.
     - source_dsource_id: The ID of the source dSource. This is mutually exclusive with source_vdb_id.
     - source_data_timestamp: The timestamp on the root ancestor timeflow from which this timeflow originated. This logical time acts as reference to the origin source data.
     - oracle_incarnation_id: Oracle-specific incarnation identifier for this timeflow.
     - oracle_cdb_timeflow_id: A reference to the mirror CDB timeflow if this is a timeflow for a PDB.
     - oracle_tde_uuid: The unique identifier for timeflow-specific TDE objects that reside outside of Delphix storage.
     - mssql_database_guid: MSSQL-specific recovery branch identifier for this timeflow.
     - is_active: Whether this timeflow is currently active or not.
     - creation_timestamp: The time when the timeflow was created.
     - activation_timestamp: The time when this timeflow became active.
     - tags: No description

    How to use filter_expresssion: 
    A request body containing a filter expression. This enables searching
    for items matching arbitrarily complex conditions. The list of
    attributes which can be used in filter expressions is available
    in the x-filterable vendor extension.
    
    # Filter Expression Overview
    **Note: All keywords are case-insensitive**
    
    ## Comparison Operators
    | Operator | Description | Example |
    | --- | --- | --- |
    | CONTAINS | Substring or membership testing for string and list attributes respectively. | field3 CONTAINS 'foobar', field4 CONTAINS TRUE  |
    | IN | Tests if field is a member of a list literal. List can contain a maximum of 100 values | field2 IN ['Goku', 'Vegeta'] |
    | GE | Tests if a field is greater than or equal to a literal value | field1 GE 1.2e-2 |
    | GT | Tests if a field is greater than a literal value | field1 GT 1.2e-2 |
    | LE | Tests if a field is less than or equal to a literal value | field1 LE 9000 |
    | LT | Tests if a field is less than a literal value | field1 LT 9.02 |
    | NE | Tests if a field is not equal to a literal value | field1 NE 42 |
    | EQ | Tests if a field is equal to a literal value | field1 EQ 42 |
    
    ## Search Operator
    The SEARCH operator filters for items which have any filterable
    attribute that contains the input string as a substring, comparison
    is done case-insensitively. This is not restricted to attributes with
    string values. Specifically `SEARCH '12'` would match an item with an
    attribute with an integer value of `123`.
    
    ## Logical Operators
    Ordered by precedence.
    | Operator | Description | Example |
    | --- | --- | --- |
    | NOT | Logical NOT (Right associative) | NOT field1 LE 9000 |
    | AND | Logical AND (Left Associative) | field1 GT 9000 AND field2 EQ 'Goku' |
    | OR | Logical OR (Left Associative) | field1 GT 9000 OR field2 EQ 'Goku' |
    
    ## Grouping
    Parenthesis `()` can be used to override operator precedence.
    
    For example:
    NOT (field1 LT 1234 AND field2 CONTAINS 'foo')
    
    ## Literal Values
    | Literal      | Description | Examples |
    | --- | --- | --- |
    | Nil | Represents the absence of a value | nil, Nil, nIl, NIL |
    | Boolean | true/false boolean | true, false, True, False, TRUE, FALSE |
    | Number | Signed integer and floating point numbers. Also supports scientific notation. | 0, 1, -1, 1.2, 0.35, 1.2e-2, -1.2e+2 |
    | String | Single or double quoted | "foo", "bar", "foo bar", 'foo', 'bar', 'foo bar' |
    | Datetime | Formatted according to [RFC3339](https://datatracker.ietf.org/doc/html/rfc3339) | 2018-04-27T18:39:26.397237+00:00 |
    | List | Comma-separated literals wrapped in square brackets | [0], [0, 1], ['foo', "bar"] |
    
    ## Limitations
    - A maximum of 8 unique identifiers may be used inside a filter expression.
    
    """
    # Build parameters excluding None values
    params = build_params(limit=limit, cursor=cursor, sort=sort)
    search_body = {'filter_expression': filter_expression}
    return make_api_request('POST', '/timeflows/search', params=params, json_body=search_body)

@log_tool_execution
def search_vdb_groups(limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None, filter_expression: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for VDB Groups.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.(optional)
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.(optional)
    :param sort: The field to sort results by. A property name with a prepended '-' signifies descending order.
    :param sort: The field to sort results by. A property name with a prepended '-' signifies descending order.(optional)
    :param filter_expression: Filter expression string (optional)
    Filter expression can include the following fields:
     - id: A unique identifier for the entity.
     - name: A unique name for the entity.
     - vdb_ids: The list of VDB IDs in this VDB Group.
     - is_locked: Indicates whether the VDB Group is locked.
     - locked_by: The Id of the account that locked the VDB Group.
     - locked_by_name: The name of the account that locked the VDB Group.
     - vdb_group_source: Source of the vdb group, default is DCT. In case of self-service container, this value would be ENGINE.
     - ss_data_layout_id: Data-layout Id for engine-managed vdb groups.
     - vdbs: Dictates order of operations on VDBs. Operations can be performed in parallel <br> for all VDBs or sequentially. Below are possible valid and invalid orderings given an example <br> VDB group with 3 vdbs (A, B, and C).<br> Valid:<br> {"vdb_id":"vdb-1", "order":"1"} {"vdb_id":"vdb-2", order:"1"} {vdb_id:"vdb-3", order:"1"} (parallel)<br> {vdb_id:"vdb-1", order:"1"} {vdb_id:"vdb-2", order:"2"} {vdb_id:"vdb-3", order:"3"} (sequential)<br> Invalid:<br> {vdb_id:"vdb-1", order:"A"} {vdb_id:"vdb-2", order:"B"} {vdb_id:"vdb-3", order:"C"} (sequential)<br><br> In the sequential case the vdbs with priority 1 is the first to be started and the last to<br> be stopped. This value is set on creation of VDB groups.
     - database_type: The database type of the VDB Group. If all VDBs in the group are of the same database_type, this field will be set to that type. If the VDBs are of different database_type, this field will be set to 'Mixed'.
     - status: The status of the VDB Group. If all VDBs in the VDB Group have the same status, this field will be set to that status. If the VDBs have different statuses, this field will be set to 'Mixed'.
     - last_successful_refresh_to_bookmark_id: The bookmark ID to which the VDB Group was last successfully refreshed.
     - last_successful_refresh_time: The time at which the VDB Group was last successfully refreshed.
     - tags: No description

    How to use filter_expresssion: 
    A request body containing a filter expression. This enables searching
    for items matching arbitrarily complex conditions. The list of
    attributes which can be used in filter expressions is available
    in the x-filterable vendor extension.
    
    # Filter Expression Overview
    **Note: All keywords are case-insensitive**
    
    ## Comparison Operators
    | Operator | Description | Example |
    | --- | --- | --- |
    | CONTAINS | Substring or membership testing for string and list attributes respectively. | field3 CONTAINS 'foobar', field4 CONTAINS TRUE  |
    | IN | Tests if field is a member of a list literal. List can contain a maximum of 100 values | field2 IN ['Goku', 'Vegeta'] |
    | GE | Tests if a field is greater than or equal to a literal value | field1 GE 1.2e-2 |
    | GT | Tests if a field is greater than a literal value | field1 GT 1.2e-2 |
    | LE | Tests if a field is less than or equal to a literal value | field1 LE 9000 |
    | LT | Tests if a field is less than a literal value | field1 LT 9.02 |
    | NE | Tests if a field is not equal to a literal value | field1 NE 42 |
    | EQ | Tests if a field is equal to a literal value | field1 EQ 42 |
    
    ## Search Operator
    The SEARCH operator filters for items which have any filterable
    attribute that contains the input string as a substring, comparison
    is done case-insensitively. This is not restricted to attributes with
    string values. Specifically `SEARCH '12'` would match an item with an
    attribute with an integer value of `123`.
    
    ## Logical Operators
    Ordered by precedence.
    | Operator | Description | Example |
    | --- | --- | --- |
    | NOT | Logical NOT (Right associative) | NOT field1 LE 9000 |
    | AND | Logical AND (Left Associative) | field1 GT 9000 AND field2 EQ 'Goku' |
    | OR | Logical OR (Left Associative) | field1 GT 9000 OR field2 EQ 'Goku' |
    
    ## Grouping
    Parenthesis `()` can be used to override operator precedence.
    
    For example:
    NOT (field1 LT 1234 AND field2 CONTAINS 'foo')
    
    ## Literal Values
    | Literal      | Description | Examples |
    | --- | --- | --- |
    | Nil | Represents the absence of a value | nil, Nil, nIl, NIL |
    | Boolean | true/false boolean | true, false, True, False, TRUE, FALSE |
    | Number | Signed integer and floating point numbers. Also supports scientific notation. | 0, 1, -1, 1.2, 0.35, 1.2e-2, -1.2e+2 |
    | String | Single or double quoted | "foo", "bar", "foo bar", 'foo', 'bar', 'foo bar' |
    | Datetime | Formatted according to [RFC3339](https://datatracker.ietf.org/doc/html/rfc3339) | 2018-04-27T18:39:26.397237+00:00 |
    | List | Comma-separated literals wrapped in square brackets | [0], [0, 1], ['foo', "bar"] |
    
    ## Limitations
    - A maximum of 8 unique identifiers may be used inside a filter expression.
    
    """
    # Build parameters excluding None values
    params = build_params(limit=limit, cursor=cursor, sort=sort)
    search_body = {'filter_expression': filter_expression}
    return make_api_request('POST', '/vdb-groups/search', params=params, json_body=search_body)

@log_tool_execution
def search_vdbs(limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None, filter_expression: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for VDBs.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.
    :param limit: Maximum number of objects to return per query. The value must be between 1 and 1000. Default is 100.(optional)
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.
    :param cursor: Cursor to fetch the next or previous page of results. The value of this property must be extracted from the 'prev_cursor' or 'next_cursor' property of a PaginatedResponseMetadata which is contained in the response of list and search API endpoints.(optional)
    :param sort: The field to sort results by. A property name with a prepended '-' signifies descending order.
    :param sort: The field to sort results by. A property name with a prepended '-' signifies descending order.(optional)
    :param filter_expression: Filter expression string (optional)
    Filter expression can include the following fields:
     - id: The VDB object entity ID.
     - database_type: The database type of this VDB.
     - name: The logical name of this VDB.
     - description: The container description of this VDB.
     - database_name: The name of the database on the target environment or in the database management system.
     - namespace_id: The namespace id of this VDB.
     - namespace_name: The namespace name of this VDB.
     - is_replica: Is this a replicated object.
     - is_locked: Is this VDB locked.
     - locked_by: The ID of the account that locked this VDB.
     - locked_by_name: The name of the account that locked this VDB.
     - database_version: The database version of this VDB.
     - jdbc_connection_string: The JDBC connection URL for this VDB.
     - size: The total size of this VDB, in bytes.
     - storage_size: The actual space used by this VDB, in bytes.
     - unvirtualized_space: The disk space, in bytes, that it would take to store the VDB without Delphix.
     - engine_id: A reference to the Engine that this VDB belongs to.
     - status: The runtime status of the VDB. 'Unknown' if all attempts to connect to the dataset failed.
     - masked: The VDB is masked or not.
     - content_type: The content type of the vdb.
     - parent_timeflow_timestamp: The timestamp for parent timeflow.
     - parent_timeflow_timezone: The timezone for parent timeflow.
     - environment_id: A reference to the Environment that hosts this VDB.
     - ip_address: The IP address of the VDB's host.
     - fqdn: The FQDN of the VDB's host.
     - parent_id: A reference to the parent dataset of this VDB.
     - parent_dsource_id: A reference to the parent dSource of this VDB.
     - root_parent_id: A reference to the root parent dataset of this VDB which could be a VDB or a dSource.
     - group_name: The name of the group containing this VDB.
     - engine_name: Name of the Engine where this VDB is hosted
     - cdb_id: A reference to the CDB or VCDB associated with this VDB.
     - tags: No description
     - creation_date: The date this VDB was created.
     - hooks: No description
     - appdata_source_params: The JSON payload conforming to the DraftV4 schema based on the type of application data being manipulated.
     - template_id: A reference to the Database Template.
     - template_name: Name of the Database Template.
     - config_params: Database configuration parameter overrides.
     - environment_user_ref: The environment user reference.
     - additional_mount_points: Specifies additional locations on which to mount a subdirectory of an AppData container. Can only be updated while the VDB is disabled.
     - appdata_config_params: The parameters specified by the source config schema in the toolkit
     - mount_point: Mount point for the VDB (Oracle, ASE, AppData).
     - current_timeflow_id: A reference to the currently active timeflow for this VDB.
     - previous_timeflow_id: A reference to the previous timeflow for this VDB.
     - last_refreshed_date: The date this VDB was last refreshed.
     - vdb_restart: Indicates whether the Engine should automatically restart this vdb when target host reboot is detected.
     - is_appdata: Indicates whether this VDB has an AppData database.
     - exported_data_directory: ZFS exported data directory path.
     - vcdb_exported_data_directory: ZFS exported data directory path of the virtual CDB container (vCDB).
     - toolkit_id: The ID of the toolkit associated with this VDB.
     - plugin_version: The version of the plugin associated with this VDB.
     - primary_object_id: The ID of the parent object from which replication was done.
     - primary_engine_id: The ID of the parent engine from which replication was done.
     - primary_engine_name: The name of the parent engine from which replication was done.
     - replicas: The list of replicas replicated from this object.
     - invoke_datapatch: Indicates whether datapatch should be invoked.
     - enabled: True if VDB is enabled false if VDB is disabled.
     - node_listeners: The list of node listeners for this VDB.
     - instance_name: The instance name name of this single instance VDB.
     - instance_number: The instance number of this single instance VDB.
     - instances: No description
     - oracle_services: No description
     - repository_id: The repository id of this VDB.
     - containerization_state: No description
     - parent_tde_keystore_path: Path to a copy of the parent's Oracle transparent data encryption keystore on the target host. Required to provision from snapshots containing encrypted database files.
     - target_vcdb_tde_keystore_path: Path to the keystore of the target vCDB.
     - tde_key_identifier: ID of the key created by Delphix, as recorded in v$encryption_keys.key_id.
     - parent_pdb_tde_keystore_path: Path to a copy of the parent PDB's Oracle transparent data encryption keystore on the target host.
Required to provision from snapshots of PDB containing encrypted database files with isolated mode keystore.

     - target_pdb_tde_keystore_path: Path of the virtual PDB's Oracle transparent data encryption keystore on the target host.
     - recovery_model: Recovery model of the vdb database.
     - cdc_on_provision: Whether to enable CDC on provision for MSSql.
     - data_connection_id: The ID of the associated DataConnection.
     - mssql_ag_backup_location: Shared backup location to be used for VDB provision on AG Cluster.
     - mssql_ag_backup_based: Indicates whether to do fast operations for VDB on AG which will use a healthy secondary replica to recreate the AG or backup based operations which will use the primary replica to recreate the AG using backup and restore process.
     - mssql_ag_replicas: Indicates the mssql replica sources constitutes in MSSQL AG virtual source.
     - database_unique_name: The unique name of the database.
     - db_username: The user name of the database.
     - new_db_id: Indicates whether Delphix will generate a new DBID during VDB provision or refresh.
     - redo_log_groups: Number of Online Redo Log Groups.
     - redo_log_size_in_mb: Online Redo Log size in MB.
     - custom_env_vars: No description
     - active_instances: No description
     - nfs_version: The NFS version that was last used to mount this source."
     - nfs_version_reason: No description
     - nfs_encryption_enabled: Flag indicating whether the data transfer is encrypted or not.

    How to use filter_expresssion: 
    A request body containing a filter expression. This enables searching
    for items matching arbitrarily complex conditions. The list of
    attributes which can be used in filter expressions is available
    in the x-filterable vendor extension.
    
    # Filter Expression Overview
    **Note: All keywords are case-insensitive**
    
    ## Comparison Operators
    | Operator | Description | Example |
    | --- | --- | --- |
    | CONTAINS | Substring or membership testing for string and list attributes respectively. | field3 CONTAINS 'foobar', field4 CONTAINS TRUE  |
    | IN | Tests if field is a member of a list literal. List can contain a maximum of 100 values | field2 IN ['Goku', 'Vegeta'] |
    | GE | Tests if a field is greater than or equal to a literal value | field1 GE 1.2e-2 |
    | GT | Tests if a field is greater than a literal value | field1 GT 1.2e-2 |
    | LE | Tests if a field is less than or equal to a literal value | field1 LE 9000 |
    | LT | Tests if a field is less than a literal value | field1 LT 9.02 |
    | NE | Tests if a field is not equal to a literal value | field1 NE 42 |
    | EQ | Tests if a field is equal to a literal value | field1 EQ 42 |
    
    ## Search Operator
    The SEARCH operator filters for items which have any filterable
    attribute that contains the input string as a substring, comparison
    is done case-insensitively. This is not restricted to attributes with
    string values. Specifically `SEARCH '12'` would match an item with an
    attribute with an integer value of `123`.
    
    ## Logical Operators
    Ordered by precedence.
    | Operator | Description | Example |
    | --- | --- | --- |
    | NOT | Logical NOT (Right associative) | NOT field1 LE 9000 |
    | AND | Logical AND (Left Associative) | field1 GT 9000 AND field2 EQ 'Goku' |
    | OR | Logical OR (Left Associative) | field1 GT 9000 OR field2 EQ 'Goku' |
    
    ## Grouping
    Parenthesis `()` can be used to override operator precedence.
    
    For example:
    NOT (field1 LT 1234 AND field2 CONTAINS 'foo')
    
    ## Literal Values
    | Literal      | Description | Examples |
    | --- | --- | --- |
    | Nil | Represents the absence of a value | nil, Nil, nIl, NIL |
    | Boolean | true/false boolean | true, false, True, False, TRUE, FALSE |
    | Number | Signed integer and floating point numbers. Also supports scientific notation. | 0, 1, -1, 1.2, 0.35, 1.2e-2, -1.2e+2 |
    | String | Single or double quoted | "foo", "bar", "foo bar", 'foo', 'bar', 'foo bar' |
    | Datetime | Formatted according to [RFC3339](https://datatracker.ietf.org/doc/html/rfc3339) | 2018-04-27T18:39:26.397237+00:00 |
    | List | Comma-separated literals wrapped in square brackets | [0], [0, 1], ['foo', "bar"] |
    
    ## Limitations
    - A maximum of 8 unique identifiers may be used inside a filter expression.
    
    """
    # Build parameters excluding None values
    params = build_params(limit=limit, cursor=cursor, sort=sort)
    search_body = {'filter_expression': filter_expression}
    return make_api_request('POST', '/vdbs/search', params=params, json_body=search_body)


def register_tools(app, dct_client):
    global client
    client = dct_client
    logger.info(f'Registering tools for dataset_endpoints...')
    try:
        logger.info(f'  Registering tool function: search_bookmarks')
        app.add_tool(search_bookmarks, name="search_bookmarks")
        logger.info(f'  Registering tool function: search_data_connections')
        app.add_tool(search_data_connections, name="search_data_connections")
        logger.info(f'  Registering tool function: search_dsources')
        app.add_tool(search_dsources, name="search_dsources")
        logger.info(f'  Registering tool function: search_snapshots')
        app.add_tool(search_snapshots, name="search_snapshots")
        logger.info(f'  Registering tool function: search_sources')
        app.add_tool(search_sources, name="search_sources")
        logger.info(f'  Registering tool function: search_timeflows')
        app.add_tool(search_timeflows, name="search_timeflows")
        logger.info(f'  Registering tool function: search_vdb_groups')
        app.add_tool(search_vdb_groups, name="search_vdb_groups")
        logger.info(f'  Registering tool function: search_vdbs')
        app.add_tool(search_vdbs, name="search_vdbs")
    except Exception as e:
        logger.error(f'Error registering tools for dataset_endpoints: {e}')
    logger.info(f'Tools registration finished for dataset_endpoints.')
