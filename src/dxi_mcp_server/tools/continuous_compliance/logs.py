"""
Logs tools (Continuous Compliance)

Provides access to job logs and an explanation helper.
"""

import logging
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from ...client import DCTAPIClient

logger = logging.getLogger(__name__)


def register_logs_tools(mcp: FastMCP, client: DCTAPIClient):
    @mcp.tool()
    async def get_job_logs(job_id: str, path_override: Optional[str] = None) -> Dict[str, Any]:
        """Get logs for a job.

        Tries multiple known path patterns since DCT releases differ:
        - compliance-jobs/{job_id}/logs
        - jobs/{job_id}/logs
        - job-executions/{job_id}/logs
        - executions/{job_id}/logs

        Pass path_override to use a specific path.
        """
        candidates = [
            path_override or f"compliance-jobs/{job_id}/logs",
            f"jobs/{job_id}/logs",
            f"job-executions/{job_id}/logs",
            f"executions/{job_id}/logs",
        ]
        last_error: Optional[Dict[str, Any]] = None
        for p in candidates:
            try:
                return await client.make_request("GET", p)
            except Exception as e:
                # Capture and try next candidate
                last_error = {"error": str(e), "path": p}
                continue
        return {
            "error": "not_found",
            "message": "No logs endpoint found for this job on current DCT release.",
            "tried_paths": candidates,
            "last_error": last_error,
            "suggestions": [
                "Use path_override to specify the exact logs endpoint for your DCT.",
                "List executions for the job and try get_execution with /logs if supported.",
                "Check DCT documentation for logs API paths for this version.",
            ],
        }

    @mcp.tool()
    async def explain_job_latest_logs(job_id: str) -> Dict[str, Any]:
        """Fetch the most recent execution for a job and explain its logs.

        Strategy:
        - List executions filtered by job_id using 'executions' endpoint
        - Select the latest by end_time or start_time
        - Build a readable log_text from execution metadata and task_events
        - Return an explanation summary similar to explain_job_logs
        """
        try:
            # Fetch executions for the given job
            exec_resp = await client.make_request("GET", "executions", params={"job_id": job_id, "limit": 50})
            items = exec_resp.get("items") or exec_resp.get("results") or []
            if not items:
                return {
                    "error": "no_executions",
                    "message": "No executions found for the specified job.",
                    "job_id": job_id,
                }

            def _ts(ex):
                return ex.get("end_time") or ex.get("start_time") or ex.get("submit_time") or ""

            # Pick latest by lexicographic ISO timestamp (assumes ISO8601)
            latest = sorted(items, key=_ts, reverse=True)[0]

            # Build a concise textual representation from execution and task_events
            header_lines = []
            for k in (
                "id",
                "status",
                "engine_name",
                "masking_job_name",
                "start_time",
                "end_time",
                "run_duration",
                "total_duration",
            ):
                if k in latest and latest[k] is not None:
                    header_lines.append(f"{k}: {latest[k]}")

            events = latest.get("task_events") or []
            event_lines = [
                f"{e.get('event','')} - {e.get('status','')}" for e in events if isinstance(e, dict)
            ]

            log_text = "\n".join(header_lines + ["-- events --"] + event_lines)

            # Perform the same lightweight analysis as explain_job_logs
            lines = log_text.splitlines()
            errors = [l for l in lines if "ERROR" in l or "Error" in l]
            warnings = [l for l in lines if "WARN" in l or "Warning" in l]
            failed = [l for l in lines if "FAIL" in l or "failed" in l.lower()]

            summary = {
                "job_id": job_id,
                "execution_id": latest.get("id"),
                "status": latest.get("status"),
                "total_lines": len(lines),
                "error_count": len(errors),
                "warning_count": len(warnings),
                "failed_markers": len(failed),
                "common_patterns": {
                    "constraint": any("constraint" in l.lower() for l in errors),
                    "timeout": any("timeout" in l.lower() for l in errors + warnings),
                    "auth": any("auth" in l.lower() or "permission" in l.lower() for l in errors + warnings),
                },
                "sample_errors": errors[:5],
                "sample_warnings": warnings[:5],
                "recommendations": [
                    "Check connector credentials and network reachability for auth/timeouts.",
                    "Verify ruleset domains/algorithms for columns flagged in errors.",
                    "Review job configuration for invalid parameters or missing resources.",
                    "Search KB with top error phrases for known resolutions.",
                ],
            }
            return {"summary": summary, "raw": {"execution": latest, "text": log_text}}
        except Exception as e:
            return {"error": "explain_latest_failed", "message": str(e), "job_id": job_id}

    logger.info("Logs tools registered successfully (continuous_compliance)")


def register_log_explanation_tools(mcp: FastMCP):
    @mcp.tool()
    async def explain_job_logs(log_text: str) -> Dict[str, Any]:
        """Explain job logs: summarize and extract errors/warnings.

        Args:
            log_text: Raw log text or JSON string from job logs.
        Returns:
            Summary with counts and suggested next steps.
        """
        try:
            lines = log_text.splitlines()
            errors = [l for l in lines if "ERROR" in l or "Error" in l]
            warnings = [l for l in lines if "WARN" in l or "Warning" in l]
            failed = [l for l in lines if "FAIL" in l or "failed" in l.lower()]

            summary = {
                "total_lines": len(lines),
                "error_count": len(errors),
                "warning_count": len(warnings),
                "failed_markers": len(failed),
                "common_patterns": {
                    "constraint": any("constraint" in l.lower() for l in errors),
                    "timeout": any("timeout" in l.lower() for l in errors + warnings),
                    "auth": any("auth" in l.lower() or "permission" in l.lower() for l in errors + warnings),
                },
                "sample_errors": errors[:5],
                "sample_warnings": warnings[:5],
                "recommendations": [
                    "Check connector credentials and network reachability for auth/timeouts.",
                    "Verify ruleset domains/algorithms for columns flagged in errors.",
                    "Review job configuration for invalid parameters or missing resources.",
                    "Search KB with top error phrases for known resolutions.",
                ],
            }
            return {"summary": summary}
        except Exception as e:
            return {"error": "explain_failed", "message": str(e)}
