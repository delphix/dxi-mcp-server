"""Shared helpers for confirmation-gate integration tests (DLPXECO-14458).

These tests exercise the *real* gate wiring in ``tools/core/dynamic.py`` together
with the real confirmation stores, velocity counter, and ``manual_confirmation.txt``
rules. Only the DCT API dispatch (``dct_client.make_request``) and the cached
OpenAPI spec are stubbed — everything between the ``execute`` entry point and the
wire is the production code path.
"""

from unittest.mock import AsyncMock, MagicMock

from dct_mcp_server.tools.core.dynamic import _make_execute_fn

# Minimal spec carrying the paths the gate tests drive. Path templates are
# matched against fully-resolved paths by the spec model (e.g. "/vdbs/vdb-1"
# matches "/vdbs/{vdbId}").
GATE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "gate-test", "version": "1.0.0"},
    "paths": {
        "/vdbs/{vdbId}": {
            "patch": {
                "operationId": "updateVdb",
                "summary": "Update VDB",
                "tags": ["VDBs"],
            },
        },
        # batch_check:10:60 rule in manual_confirmation.txt (velocity detection).
        "/vdbs/{vdbId}/start": {
            "post": {
                "operationId": "startVdb",
                "summary": "Start VDB",
                "tags": ["VDBs"],
            },
        },
        # elevated rule — Tier-2 impactful op (confirm-once → run N).
        "/vdbs/{vdbId}/refresh_by_snapshot": {
            "post": {
                "operationId": "refreshVdbBySnapshot",
                "summary": "Refresh VDB by snapshot",
                "tags": ["VDBs"],
            },
        },
    },
}


def make_execute(return_value=None):
    """Return ``(execute_fn, client_mock)`` wired to a stub DCT client."""
    app = MagicMock()
    client = MagicMock()
    client.make_request = AsyncMock(return_value=return_value or {"ok": True})
    return _make_execute_fn(app, client), client
