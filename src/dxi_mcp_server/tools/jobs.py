"""
Job tools for DCT API

Schema summaries (key fields only):
- Job:
  - id, status [PENDING|STARTED|RUNNING|WAITING|COMPLETED|FAILED|CANCELED|ABANDONED|TIMEDOUT]
  - type, localized_type
  - target_id, target_name
  - start_time, update_time
  - error_details, warning_message, percent_complete, tasks[]

Endpoints covered:
- GET /jobs                         → list jobs
- POST /jobs/search                 → search jobs
- GET /jobs/{jobId}                 → get job by id
- POST /jobs/{jobId}/abandon        → abandon job
- GET/POST /jobs/{jobId}/tags       → get/create tags
- POST /jobs/{jobId}/tags/delete    → delete tags

Utilities:
- wait_for_job                      → poll until terminal state
"""

import asyncio
import logging
from typing import Any, Dict, Optional, List

from mcp.server.fastmcp import FastMCP

from ..client import DCTAPIClient

logger = logging.getLogger(__name__)


def register_job_tools(mcp: FastMCP, client: DCTAPIClient):
    """Register Job-related tools"""

    @mcp.tool()
    async def list_jobs(
        limit: Optional[int] = None, cursor: Optional[str] = None, sort: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all jobs

        Args:
            limit: Maximum number of results to return
            cursor: Pagination cursor
            sort: Sort order (default: -start_time)
        Returns:
            Object with:
            - items: list of Job objects
            - response_metadata: pagination metadata
        """
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        if sort is not None:
            params["sort"] = sort

        return await client.make_request("GET", "jobs", params=params)

    @mcp.tool()
    async def search_jobs(
        filter_expression: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search for jobs with filter expressions

        Args:
            filter_expression: Filter expression string (e.g., "status EQ 'RUNNING' AND type CONTAINS 'PROVISION'")
            limit: Maximum number of results to return
            cursor: Pagination cursor
            sort: Sort order (default: -start_time)
        Returns:
            Object with:
            - items: list of Job objects
            - response_metadata: pagination metadata
        """
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        if sort is not None:
            params["sort"] = sort

        body = {"filter_expression": filter_expression}
        return await client.make_request("POST", "jobs/search", params=params, json=body)

    @mcp.tool()
    async def get_job(job_id: str) -> Dict[str, Any]:
        """Get a job by ID"""
        return await client.make_request("GET", f"jobs/{job_id}")

    @mcp.tool()
    async def abandon_job(job_id: str) -> Dict[str, Any]:
        """Abandon a job (moves to ABANDONED terminal state without stopping work)."""
        return await client.make_request("POST", f"jobs/{job_id}/abandon")

    @mcp.tool()
    async def get_job_tags(job_id: str) -> Dict[str, Any]:
        """Get tags for a job"""
        return await client.make_request("GET", f"jobs/{job_id}/tags")

    @mcp.tool()
    async def create_job_tags(job_id: str, tags: List[Dict[str, str]]) -> Dict[str, Any]:
        """Create tags for a job

        Example: tags=[{"key": "owner", "value": "team-x"}]
        """
        body = {"tags": tags}
        return await client.make_request("POST", f"jobs/{job_id}/tags", json=body)

    @mcp.tool()
    async def delete_job_tags(job_id: str, delete_parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Delete tags for a job"""
        body: Dict[str, Any] = delete_parameters or {}
        return await client.make_request("POST", f"jobs/{job_id}/tags/delete", json=body)

    @mcp.tool()
    async def wait_for_job(
        job_id: str,
        poll_interval_seconds: float = 2.0,
        timeout_seconds: Optional[float] = 600.0,
    ) -> Dict[str, Any]:
        """Poll a job until it reaches a terminal state and return the final job object

        Terminal states: COMPLETED, FAILED, CANCELED, ABANDONED, TIMEDOUT
        """
        terminal_statuses = {"COMPLETED", "FAILED", "CANCELED", "ABANDONED", "TIMEDOUT"}
        deadline = None if timeout_seconds is None else asyncio.get_event_loop().time() + timeout_seconds

        while True:
            job = await client.make_request("GET", f"jobs/{job_id}")
            status = job.get("status")
            if status in terminal_statuses:
                return job

            if deadline is not None and asyncio.get_event_loop().time() >= deadline:
                job["status"] = job.get("status", "TIMEDOUT")
                job["error_details"] = job.get("error_details") or "wait_for_job timed out"
                return job

            await asyncio.sleep(poll_interval_seconds)

    logger.info("Job tools registered successfully")


