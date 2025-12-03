"""
Ruleset tools (Continuous Compliance)
"""

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from ...client import DCTAPIClient

logger = logging.getLogger(__name__)


def register_ruleset_tools(mcp: FastMCP, client: DCTAPIClient):
    @mcp.tool()
    async def list_rulesets(limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        if sort is not None:
            params["sort"] = sort
        return await client.make_request("GET", "rule-sets", params=params)

    @mcp.tool()
    async def search_rulesets(
        search_criteria: Dict[str, Any],
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        params = {}
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        if sort is not None:
            params["sort"] = sort
        return await client.make_request("POST", "rule-sets/search", data={"filter_expression": search_criteria}, params=params)

    @mcp.tool()
    async def get_ruleset(ruleset_id: str) -> Dict[str, Any]:
        return await client.make_request("GET", f"rule-sets/{ruleset_id}")

    @mcp.tool()
    async def create_ruleset(*args, **kwargs) -> Dict[str, Any]:
        return {
            "error": "not_supported",
            "message": "Ruleset creation is not currently supported on this DCT instance.",
            "details": "The operation 'RULE_SET_CREATE' is not supported on this DCT release.",
            "status": "feature_unavailable",
        }

    @mcp.tool()
    async def update_ruleset(ruleset_id: str, *args, **kwargs) -> Dict[str, Any]:
        return {
            "error": "not_supported",
            "message": "Ruleset updates are not currently supported on this DCT instance.",
            "details": "The operation 'RULE_SET_UPDATE' is not supported on this DCT release.",
            "ruleset_id": ruleset_id,
            "status": "feature_unavailable",
        }

    logger.info("Ruleset tools registered successfully (continuous_compliance)")
