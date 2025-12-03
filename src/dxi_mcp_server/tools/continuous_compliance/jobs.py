"""
Jobs tools (Continuous Compliance)

Provides read-only access to compliance jobs.
"""

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from ...client import DCTAPIClient

logger = logging.getLogger(__name__)


def register_jobs_tools(mcp: FastMCP, client: DCTAPIClient):
    @mcp.tool()
    async def list_jobs(limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None) -> Dict[str, Any]:
        """List compliance jobs"""
        params = {}
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        if sort is not None:
            params["sort"] = sort
        # Known working endpoint from prior tests
        return await client.make_request("GET", "compliance-jobs", params=params)

    @mcp.tool()
    async def get_job(job_id: str) -> Dict[str, Any]:
        """Get a job by ID"""
        return await client.make_request("GET", f"compliance-jobs/{job_id}")

    @mcp.tool()
    async def create_profile_job(
        name: str,
        connector_id: str,
        ruleset_id: Optional[str] = None,
        rule_set_id: Optional[str] = None,
        profile_set_id: Optional[str] = None,
        policy_id: Optional[str] = None,
        schedule: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        job_type: Optional[str] = "profile",
    ) -> Dict[str, Any]:
        """Create a new profile job (compliance job).

        Notes:
        - This posts to 'compliance-jobs' with provided payload.
        - Provide either ruleset_id or profile_set_id/policy_id depending on your workflow.
        - The exact required fields may vary per DCT release; errors will surface from API.
        """
        # Current DCT release returns 501 Not Implemented for job creation.
        # Return a clear, structured response consistent with other unsupported operations.
        return {
            "error": "not_supported",
            "message": "Profile job creation is not supported on this DCT release.",
            "details": "The API operation 'COMPLIANCE_JOB_CREATE' is not implemented (HTTP 501) on this environment.",
            "status": "feature_unavailable",
            "suggestions": [
                "Create the profiling job via the DCT UI.",
                "Verify DCT version supports compliance job API operations.",
                "Upgrade to a newer DCT version if API-based creation is required.",
            ],
        }

    @mcp.tool()
    async def update_profile_job(
        job_id: str,
        name: Optional[str] = None,
        ruleset_id: Optional[str] = None,
        rule_set_id: Optional[str] = None,
        profile_set_id: Optional[str] = None,
        policy_id: Optional[str] = None,
        schedule: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an existing profile job.

        Sends PATCH to 'compliance-jobs/{job_id}' with provided fields.
        """
        # Current DCT release indicates job update operations are not available.
        return {
            "error": "not_supported",
            "message": "Profile job update is not supported on this DCT release.",
            "details": "The API operation 'COMPLIANCE_JOB_UPDATE' is not implemented on this environment.",
            "job_id": job_id,
            "status": "feature_unavailable",
            "suggestions": [
                "Modify the profiling job via the DCT UI.",
                "Verify DCT version supports compliance job update operations.",
                "Upgrade to a newer DCT version if API-based updates are required.",
            ],
        }

    logger.info("Jobs tools registered successfully (continuous_compliance)")
