"""
Engine tools for DCT API

Schema summaries (key fields only):
- RegisteredEngine:
  - id, uuid, type, name, hostname
  - version, cpu_core_count, memory_size
  - data_storage_capacity, data_storage_used
  - insecure_ssl, unsafe_ssl_hostname_check
  - status, username, connection_status, engine_connection_status
  - tags[]
- PaginatedResponseMetadata: prev_cursor, next_cursor, total
"""

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from ..client import DCTAPIClient

logger = logging.getLogger(__name__)


def register_engine_tools(mcp: FastMCP, client: DCTAPIClient):
    """Register Engine-related tools"""

    @mcp.tool()
    async def list_engines(
        limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all engines

        Args:
            limit: Maximum number of results to return
            cursor: Pagination cursor
            sort: Sort order
        Returns:
            Object with:
            - items: list of RegisteredEngine objects
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
            "GET", "management/engines", params=params
        )

    @mcp.tool()
    async def search_engines(
        filter_expression: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search for engines with filter expressions

        Args:
            filter_expression: Filter expression string (e.g., "name CONTAINS 'prod' AND status EQ 'online'")
            limit: Maximum number of results to return
            cursor: Pagination cursor
            sort: Sort order

        Available filterable fields:
            - id
            - uuid
            - ssh_public_key
            - type
            - version
            - name
            - hostname
            - cpu_core_count
            - memory_size
            - data_storage_capacity
            - data_storage_used
            - insecure_ssl
            - unsafe_ssl_hostname_check
            - hyperscale_truststore_filename
            - status
            - username
            - hashicorp_vault_id
            - tags (key, value)
            - connection_status
            - connection_status_details
            - engine_connection_status
            - engine_connection_status_details

        Literal values (per API docs):
            - Nil: nil (case-insensitive)
            - Boolean: true, false (unquoted)
            - Number: 0, 1, -1, 1.2, 1.2e-2 (unquoted)
            - String: quoted, e.g., 'foo', "bar"
            - Datetime: RFC3339 literal without quotes, e.g., 2018-04-27T18:39:26.397237+00:00
            - List: [0], [0, 1], ['foo', "bar"]

        Important:
            - Quote strings; do NOT quote datetimes.
            - Example: version GE 2024-01-01T00:00:00.000Z (if a datetime field is applicable)

        Returns:
            Object with:
            - items: list of RegisteredEngine objects
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
                "management/engines/search",
                params=params,
                json=search_body,
            )
            logger.info(
                f"Found {len(result.get('items', []))} engines matching filter expression"
            )
            return result

        except Exception as e:
            logger.error(f"Error searching engines: {str(e)}")
            raise

    @mcp.tool()
    async def get_engine(engine_id: str) -> Dict[str, Any]:
        """Get engine details

        Args:
            engine_id: Engine ID
        Returns:
            RegisteredEngine object
        """
        return await client.make_request("GET", f"management/engines/{engine_id}")

    logger.info("Engine tools registered successfully")
