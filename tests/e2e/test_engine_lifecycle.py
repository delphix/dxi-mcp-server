"""
Layer 4 — real-DCT MUTATION lifecycle for the continuous_data_admin (CDA) toolset:
engine register -> verify -> unregister.

Mirrors tests/e2e/test_bookmark_lifecycle.py but for the admin persona. Engine
registration is the CDA equivalent of a fully-managed create+delete lifecycle.

GATED: skipped unless E2E_ALLOW_MUTATION=1 — and run only against a disposable /
cloned DCT. Also skipped unless E2E_ENGINE_JSON supplies the register payload.

Engine register fields are DCT-shape dependent, so the FULL register body is passed
as a JSON env var E2E_ENGINE_JSON, e.g.:
    E2E_ENGINE_JSON='{"hostname":"eng.example.com","type":"UNMASKED","username":"admin","password":"..."}'
It is parsed and splatted as kwargs into engine_tool(action="register", **payload).

Engines are matched by the hostname from the payload (no tags). Assertions are kept
resilient — this is unvalidated against a live DCT and will be tuned on first real run.

Run:  E2E_ALLOW_MUTATION=1 E2E_ENGINE_JSON='{...}' \\
      dct-mcp-test --layer e2e --base-url https://<dct> --api-key <key>
"""

import json
import os
import time

import pytest
from fastmcp import Client

from tests.e2e.conftest import build_real_transport

pytestmark = [pytest.mark.real_dct, pytest.mark.asyncio]

_TOOLSET = "continuous_data_admin"
_MUTATION = os.environ.get("E2E_ALLOW_MUTATION") == "1"
_SKIP_MUTATION = "E2E_ALLOW_MUTATION=1 not set — this test registers+unregisters a real engine."

# Poll budget for the register job (best-effort; engine register returns a job).
_JOB_TERMINAL = {"COMPLETED", "FAILED", "CANCELED", "ABANDONED", "SUSPENDED"}
_JOB_POLL_TIMEOUT = 300  # seconds
_JOB_POLL_INTERVAL = 5  # seconds


def _payload(result):
    sc = result.structured_content or {}
    return sc.get("result", sc)


def _find_job_id(body):
    """Engine register returns a job ref under one of a few common keys."""
    if not isinstance(body, dict):
        return None
    for key in ("job_id", "jobId", "id"):
        val = body.get(key)
        if isinstance(val, str):
            return val
    job = body.get("job")
    if isinstance(job, dict):
        return job.get("id") or job.get("job_id") or job.get("jobId")
    return None


async def _poll_job(client, job_id):
    """Best-effort poll of job_tool until terminal or timeout. Never asserts."""
    deadline = time.monotonic() + _JOB_POLL_TIMEOUT
    while time.monotonic() < deadline:
        res = await client.call_tool("job_tool", {"action": "get", "job_id": job_id})
        if res.is_error:
            return None
        status = _payload(res).get("status")
        if status in _JOB_TERMINAL:
            return status
        time.sleep(_JOB_POLL_INTERVAL)
    return None


@pytest.mark.skipif(not _MUTATION, reason=_SKIP_MUTATION)
async def test_engine_register_verify_unregister():
    raw = os.environ.get("E2E_ENGINE_JSON")
    if not raw:
        pytest.skip("set E2E_ENGINE_JSON to the engine register payload")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        pytest.skip(f"E2E_ENGINE_JSON is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        pytest.skip("E2E_ENGINE_JSON must be a JSON object of engine register fields")
    hostname = payload.get("hostname")
    if not hostname:
        pytest.skip("E2E_ENGINE_JSON must include a 'hostname' to match the engine by")

    async with Client(build_real_transport(_TOOLSET)) as client:
        # --- REGISTER (returns a job; poll to terminal, best-effort) ---
        created = await client.call_tool("engine_tool", {"action": "register", **payload})
        assert not created.is_error, f"engine register failed: {created}"
        job_id = _find_job_id(_payload(created))
        if job_id:
            await _poll_job(client, job_id)

        # --- VERIFY via an independent search (match by hostname) ---
        found = await client.call_tool("engine_tool", {"action": "search", "limit": 500})
        assert not found.is_error, f"engine search failed: {found}"
        matches = [
            e for e in _payload(found).get("items", []) if e.get("hostname") == hostname
        ]
        assert matches, f"registered engine {hostname!r} not found on real DCT"
        engine_id = matches[0].get("id")
        assert engine_id, f"matched engine has no id: {matches[0]}"

        # --- UNREGISTER (DELETE is manual-confirmation gated -> pre-confirm) ---
        removed = await client.call_tool(
            "engine_tool",
            {"action": "unregister", "engineId": engine_id, "confirmed": True},
        )
        assert not removed.is_error, f"engine unregister failed: {removed}"

        # --- VERIFY gone ---
        after = await client.call_tool("engine_tool", {"action": "search", "limit": 500})
        assert not after.is_error
        still = [e for e in _payload(after).get("items", []) if e.get("id") == engine_id]
        assert not still, f"engine {engine_id} still present after unregister"
