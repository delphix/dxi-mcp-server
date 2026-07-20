"""
Layer 3b — job workflow.

Translates `.claude/test/testing/self_service.md` prompts 57-60:

    57. Search for all jobs
    58. Get the first job's details
    59. Abandon the first running job
    60. Get the tags for the first job

NOTE on prompt 59: the scenario text says abandon "first call returns
confirmation; confirm to proceed", but `config/mappings/manual_confirmation.txt`
has NO rule for POST /jobs/{jobId}/abandon — so the tool does NOT gate and we
do not pass confirmed=True. (Reported as a doc/config mismatch, not a code bug.)
"""

import pytest

from tests.functional.workflows._helpers import payload, first_id


@pytest.mark.asyncio
async def test_job_workflow(mcp_client_self_service, dct_stub):
    client = mcp_client_self_service

    # Prompt 57 — Search for all jobs.
    res = await client.call_tool("job_tool", {"action": "search", "limit": 10})
    assert not res.is_error, f"search failed: {res}"
    assert dct_stub.received_request("POST", "/dct/v3/jobs/search")
    job_id = first_id(res)

    # Prompt 58 — Get the first job's details.
    res = await client.call_tool("job_tool", {"action": "get", "job_id": job_id})
    assert not res.is_error
    assert payload(res).get("id") == job_id
    assert dct_stub.received_request("GET", f"/dct/v3/jobs/{job_id}")

    # Prompt 59 — Abandon the first job (no confirmation rule -> direct call).
    res = await client.call_tool("job_tool", {"action": "abandon", "job_id": job_id})
    assert not res.is_error
    assert dct_stub.received_request("POST", f"/dct/v3/jobs/{job_id}/abandon")

    # Prompt 60 — Get the tags for the first job.
    res = await client.call_tool("job_tool", {"action": "get_tags", "job_id": job_id})
    assert not res.is_error
    assert dct_stub.received_request("GET", f"/dct/v3/jobs/{job_id}/tags")
