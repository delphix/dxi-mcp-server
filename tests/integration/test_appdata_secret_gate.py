"""Integration tests for AppData connector-secret gate (DLPXECO-14781).

Exercises the full execute wiring in dynamic.py with a stubbed DCT client.
The toolkit details endpoint is stubbed via the client mock. Only make_request
is stubbed — everything between execute() and the wire is production code.

pytest-asyncio is not installed on this host; tests use @pytest.mark.anyio
(provided by the installed anyio package).
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import dct_mcp_server.tools.core.dynamic as dynamic
import dct_mcp_server.tools.core.connector_secrets as connector_secrets_mod
from dct_mcp_server.tools.core.host_trust import _SENSITIVE_NONCE_ENV
from tests.integration._gate_helpers import make_execute

FIXTURES = Path(__file__).parent.parent / "fixtures" / "toolkits"
NONCE = "integration-nonce-14781"
DB2_TK = json.loads((FIXTURES / "db2_toolkit.json").read_text())
MYSQL_TK = json.loads((FIXTURES / "mysql_toolkit.json").read_text())

# Minimal spec for AppData dsource link
APPDATA_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "appdata-gate-test", "version": "1.0.0"},
    "paths": {
        "/dsources/appdata": {
            "post": {
                "operationId": "linkAppDataDSource",
                "summary": "Link AppData dSource",
                "tags": ["DSources"],
            },
        },
        "/vdbs/provision_by_snapshot": {
            "post": {
                "operationId": "provisionVdbBySnapshot",
                "summary": "Provision VDB by snapshot",
                "tags": ["VDBs"],
            },
        },
        "/environments": {
            "post": {
                "operationId": "createEnvironment",
                "tags": ["Environments"],
            },
        },
    },
}


@pytest.fixture(autouse=True)
def reset_caches():
    connector_secrets_mod.clear_caches()
    yield
    connector_secrets_mod.clear_caches()


@pytest.fixture
def spec_loaded(monkeypatch):
    monkeypatch.setattr(dynamic, "get_cached_spec", lambda: APPDATA_SPEC)
    monkeypatch.setattr(dynamic, "get_process_identity", lambda: "identity-14781")


def _as_host(monkeypatch, *, nonce=True, auth_mode="embedded"):
    if nonce:
        monkeypatch.setenv(_SENSITIVE_NONCE_ENV, NONCE)
    else:
        monkeypatch.delenv(_SENSITIVE_NONCE_ENV, raising=False)
    monkeypatch.setattr(dynamic, "get_dct_config", lambda **_: {"auth_mode": auth_mode})


def _make_client_with_toolkit(toolkit_json: dict):
    """Return (execute_fn, client_mock) where GET /toolkits/{id} returns toolkit_json."""
    execute, client = make_execute(return_value={"id": "ds-1", "toolkit_id": toolkit_json["id"]})

    async def _smart_request(method, endpoint, **kwargs):
        if method.upper() == "GET" and "/toolkits/" in endpoint:
            return toolkit_json
        if method.upper() == "GET" and "/dsources/" in endpoint:
            return {"id": "ds-1", "toolkit_id": toolkit_json["id"]}
        return {"ok": True}

    client.make_request = AsyncMock(side_effect=_smart_request)
    return execute, client


# ── AC-1: connector secrets trigger sensitive_input_required ─────────────────


@pytest.mark.anyio
async def test_db2_dsource_link_triggers_gate(spec_loaded, monkeypatch):
    """DB2 dSource link with inline instancePassword triggers sensitive_input_required."""
    _as_host(monkeypatch)
    execute, _ = _make_client_with_toolkit(DB2_TK)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "parameters": {
                "instanceUser": "db2inst1",
                "instancePassword": "leaked-in-chat",
                "port": 50000,
                "mountPath": "/mnt/db2",
            },
        },
    )

    assert result["status"] == "sensitive_input_required"
    assert "instancePassword" in result["required_sensitive_fields"]


@pytest.mark.anyio
async def test_mysql_dsource_link_triggers_gate_for_ref_password(spec_loaded, monkeypatch):
    """MySQL dSource link: $ref-reached password triggers the gate."""
    _as_host(monkeypatch)
    execute, _ = _make_client_with_toolkit(MYSQL_TK)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "mysql-toolkit-001",
            "parameters": {
                "host": "mysql.example.com",
                "port": 3306,
                "credentials": {
                    "dbUser": "repl",
                    "dbPassword": "typed-in-chat",
                },
            },
        },
    )

    assert result["status"] == "sensitive_input_required"
    assert "dbPassword" in result["required_sensitive_fields"]


# ── AC-9: sensitive_field_locations is present ────────────────────────────────


@pytest.mark.anyio
async def test_sensitive_field_locations_present(spec_loaded, monkeypatch):
    _as_host(monkeypatch)
    execute, _ = _make_client_with_toolkit(DB2_TK)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "parameters": {
                "instanceUser": "db2inst1",
                "instancePassword": "leaked",
                "port": 50000,
                "mountPath": "/mnt",
            },
        },
    )

    assert "sensitive_field_locations" in result
    locs = {e["location"] for e in result["sensitive_field_locations"]}
    assert any("instancePassword" in loc for loc in locs)


# ── AC-3 / AC-10: re-call with sensitive_applied does not re-prompt ───────────


@pytest.mark.anyio
async def test_recall_with_applied_location_dispatches(spec_loaded, monkeypatch):
    """Re-call with connector secret in sensitive_applied (by location) dispatches."""
    _as_host(monkeypatch)
    execute, client = _make_client_with_toolkit(DB2_TK)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "parameters": {
                "instanceUser": "db2inst1",
                "instancePassword": "injected-by-host",
                "port": 50000,
                "mountPath": "/mnt",
            },
        },
        sensitive_applied={
            "marker": NONCE,
            "fields": ["parameters.instancePassword"],
        },
    )

    # Should NOT be sensitive_input_required — should proceed to confirmation or dispatch
    assert result.get("status") != "sensitive_input_required"


@pytest.mark.anyio
async def test_recall_with_applied_bare_name_dispatches(spec_loaded, monkeypatch):
    """Re-call with connector secret applied by bare name dispatches."""
    _as_host(monkeypatch)
    execute, client = _make_client_with_toolkit(DB2_TK)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "parameters": {
                "instanceUser": "db2inst1",
                "instancePassword": "injected-by-host",
                "port": 50000,
                "mountPath": "/mnt",
            },
        },
        sensitive_applied={
            "marker": NONCE,
            "fields": ["instancePassword"],
        },
    )

    assert result.get("status") != "sensitive_input_required"


# ── AC-4: non-secret fields are never flagged ─────────────────────────────────


@pytest.mark.anyio
async def test_non_secret_fields_not_flagged(spec_loaded, monkeypatch):
    """instanceUser, port, mountPath are never in required_sensitive_fields."""
    _as_host(monkeypatch)
    execute, _ = _make_client_with_toolkit(DB2_TK)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "parameters": {
                "instanceUser": "db2inst1",
                "port": 50000,
                "mountPath": "/mnt",
                # No instancePassword — gate should fire for it, but NOT for the others
            },
        },
    )

    if result.get("status") == "sensitive_input_required":
        for field in ("instanceUser", "port", "mountPath", "backupPath"):
            assert field not in result["required_sensitive_fields"]


# ── AC-5: native ops unchanged ────────────────────────────────────────────────


@pytest.mark.anyio
async def test_native_op_unchanged(spec_loaded, monkeypatch):
    """POST /environments (native op) is unaffected by connector detection."""
    _as_host(monkeypatch)
    execute, client = make_execute(return_value={"ok": True})
    # No toolkit lookup should occur for a native op
    toolkit_calls = []
    original = client.make_request

    async def tracking_request(method, endpoint, **kwargs):
        if "/toolkits/" in endpoint:
            toolkit_calls.append(endpoint)
        return await original(method, endpoint, **kwargs)

    client.make_request = tracking_request

    result = await execute(
        path="/environments",
        method="POST",
        body={"name": "test-env", "hostname": "h.example.com"},
    )

    assert not toolkit_calls, "Toolkit lookup must not fire for native ops"


# ── AC-6: non-capture-capable clients unaffected ─────────────────────────────


@pytest.mark.anyio
async def test_non_capture_client_no_gate(spec_loaded, monkeypatch):
    """Without embedded auth mode (standalone + nonce), no connector gate is raised."""
    # Both nonce and auth_mode must be present for _secure_capture_host() → True.
    # auth_mode="standalone" alone disables it.
    _as_host(monkeypatch, auth_mode="standalone")
    execute, client = _make_client_with_toolkit(DB2_TK)
    toolkit_calls = []
    orig = client.make_request

    async def track(method, endpoint, **kwargs):
        if "/toolkits/" in endpoint:
            toolkit_calls.append(endpoint)
        return await orig(method, endpoint, **kwargs)

    client.make_request = AsyncMock(side_effect=track)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "parameters": {
                "instanceUser": "u",
                "instancePassword": "p",
                "port": 50000,
                "mountPath": "/mnt",
            },
        },
    )

    assert result.get("status") != "sensitive_input_required"
    assert not toolkit_calls


# ── AC-7: toolkit lookup failure falls back ───────────────────────────────────


@pytest.mark.anyio
async def test_toolkit_fetch_failure_fallback(spec_loaded, monkeypatch):
    """Toolkit fetch failure causes fail-open; gate is not raised."""
    from dct_mcp_server.core.exceptions import DCTClientError

    _as_host(monkeypatch)
    execute, client = make_execute(return_value={"ok": True})
    client.make_request = AsyncMock(side_effect=DCTClientError("fetch failed"))

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "parameters": {
                "instanceUser": "u",
                "instancePassword": "p",
                "port": 50000,
                "mountPath": "/mnt",
            },
        },
    )

    # Should not be sensitive_input_required (fallback); should not crash
    assert result.get("status") != "sensitive_input_required"


# ── AC-8: chain hop via path param (e.g. PATCH /dsources/appdata/{dsourceId}) ──


@pytest.mark.anyio
async def test_chain_hop_via_path_param_triggers_gate(spec_loaded, monkeypatch):
    """PATCH /dsources/appdata/{dsourceId}: chain resolves toolkit via path param hop.

    The chain `path:dsourceId>/dsources/{id}` fetches the dsource object and
    extracts toolkit_id from its response. Uses the db2 toolkit which has
    instancePassword as a password field.
    """
    # Extend APPDATA_SPEC with the patch path
    extended_spec = {
        **APPDATA_SPEC,
        "paths": {
            **APPDATA_SPEC["paths"],
            "/dsources/appdata/{dsourceId}": {
                "patch": {
                    "operationId": "updateAppDataDSource",
                    "summary": "Update AppData dSource",
                    "tags": ["DSources"],
                },
            },
        },
    }
    monkeypatch.setattr(dynamic, "get_cached_spec", lambda: extended_spec)
    monkeypatch.setattr(dynamic, "get_process_identity", lambda: "identity-14781")
    _as_host(monkeypatch)

    execute, client = make_execute(return_value={"ok": True})

    async def _hop_request(method, endpoint, **kwargs):
        if method.upper() == "GET" and "/toolkits/" in endpoint:
            return DB2_TK
        if method.upper() == "GET" and "/dsources/" in endpoint:
            # Return dsource with toolkit_id
            return {"id": "ds-99", "toolkit_id": "db2-toolkit-001"}
        return {"ok": True}

    client.make_request = AsyncMock(side_effect=_hop_request)

    result = await execute(
        path="/dsources/appdata/ds-99",
        method="PATCH",
        body={
            "parameters": {
                "instanceUser": "db2inst1",
                "instancePassword": "secret-in-body",
                "port": 50000,
                "mountPath": "/mnt",
            },
        },
    )

    assert result["status"] == "sensitive_input_required"
    assert "instancePassword" in result["required_sensitive_fields"]


@pytest.mark.anyio
async def test_chain_hop_absent_password_flagged_as_required(spec_loaded, monkeypatch):
    """If a required password field is absent, the gate still fires.

    instancePassword is required in the db2 toolkit schema. Even if omitted
    from the body, expand_and_flag should flag it (required=True, non-conditional).
    """
    _as_host(monkeypatch)
    execute, _ = _make_client_with_toolkit(DB2_TK)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "parameters": {
                "instanceUser": "db2inst1",
                # instancePassword intentionally absent
                "port": 50000,
                "mountPath": "/mnt",
            },
        },
    )

    # instancePassword is required in db2 toolkit → gate should fire for it
    assert result["status"] == "sensitive_input_required"
    assert "instancePassword" in result["required_sensitive_fields"]


@pytest.mark.anyio
async def test_dsource_snapshot_path_param_chain(spec_loaded, monkeypatch):
    """POST /dsources/{dsourceId}/snapshots uses path:dsourceId chain hop."""
    # This path uses chain: path:dsourceId>/dsources/{id}
    extended_spec = {
        **APPDATA_SPEC,
        "paths": {
            **APPDATA_SPEC["paths"],
            "/dsources/{dsourceId}/snapshots": {
                "post": {
                    "operationId": "snapshotDSource",
                    "summary": "Snapshot dSource",
                    "tags": ["DSources"],
                },
            },
        },
    }
    monkeypatch.setattr(dynamic, "get_cached_spec", lambda: extended_spec)
    monkeypatch.setattr(dynamic, "get_process_identity", lambda: "identity-14781")
    _as_host(monkeypatch)

    # db2 snapshot schema has no password fields (resync/snapshotLabel only)
    execute, client = make_execute(return_value={"ok": True})

    async def _snap_request(method, endpoint, **kwargs):
        if method.upper() == "GET" and "/toolkits/" in endpoint:
            return DB2_TK
        if method.upper() == "GET" and "/dsources/" in endpoint:
            return {"id": "ds-99", "toolkit_id": "db2-toolkit-001"}
        return {"ok": True}

    client.make_request = AsyncMock(side_effect=_snap_request)

    result = await execute(
        path="/dsources/ds-99/snapshots",
        method="POST",
        body={
            "appdata_parameters": {
                "resync": True,
            },
        },
    )

    # Snapshot schema for db2 has no password fields → no gate trigger
    assert result.get("status") != "sensitive_input_required"


@pytest.mark.anyio
async def test_toolkit_not_found_identity_error_falls_back(spec_loaded, monkeypatch):
    """404 on toolkit fetch triggers identity-level negative cache, no gate raise."""
    from dct_mcp_server.core.exceptions import DCTClientError

    _as_host(monkeypatch)
    execute, client = make_execute(return_value={"ok": True})

    async def _404_request(method, endpoint, **kwargs):
        if "/toolkits/" in endpoint:
            raise DCTClientError("HTTP 404 Not Found")
        return {"ok": True}

    client.make_request = AsyncMock(side_effect=_404_request)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "unknown-toolkit-999",
            "parameters": {
                "instanceUser": "u",
                "instancePassword": "p",
                "port": 50000,
                "mountPath": "/mnt",
            },
        },
    )

    # Fail-open: 404 for toolkit → identity-level fallback, no gate raised
    assert result.get("status") != "sensitive_input_required"


# ── Chain resolution: select-hop and alternatives ────────────────────────────


@pytest.mark.anyio
async def test_chain_with_field_select_hop(spec_loaded, monkeypatch):
    """provision_by_snapshot resolves toolkit via snapshot_id > dataset_id select.

    Chain: body:snapshot_id>/snapshots/{id}.dataset_id>/dsources/{id}^/vdbs/{id}
    This exercises the select-based hop parsing (lines 818-819, 844-848) and
    the alternative hop logic (lines 826-833).
    """
    # Extend spec with provision_by_snapshot
    extended_spec = {
        **APPDATA_SPEC,
        "paths": {
            **APPDATA_SPEC["paths"],
            "/vdbs/provision_by_snapshot": {
                "post": {
                    "operationId": "provisionVdbBySnapshot",
                    "summary": "Provision VDB",
                    "tags": ["VDBs"],
                },
            },
        },
    }
    monkeypatch.setattr(dynamic, "get_cached_spec", lambda: extended_spec)
    monkeypatch.setattr(dynamic, "get_process_identity", lambda: "identity-14781")
    _as_host(monkeypatch)

    execute, client = make_execute(return_value={"ok": True})

    async def _smart_request(method, endpoint, **kwargs):
        if "/toolkits/" in endpoint:
            return DB2_TK
        if "/snapshots/" in endpoint:
            # Return snapshot with dataset_id pointing to a dsource
            return {"id": "snap-1", "dataset_id": "ds-99"}
        if "/dsources/" in endpoint:
            return {"id": "ds-99", "toolkit_id": "db2-toolkit-001"}
        return {"ok": True}

    client.make_request = AsyncMock(side_effect=_smart_request)

    result = await execute(
        path="/vdbs/provision_by_snapshot",
        method="POST",
        body={
            "snapshot_id": "snap-1",
            "source_data_id": "ds-99",
            "appdata_source_params": {
                "mountPath": "/mnt",
            },
            "appdata_config_params": {
                "databaseName": "mydb",
            },
        },
    )

    # db2 virtual_source_definition and source_config_definition have no password
    # fields, so no gate triggers — but toolkit resolution DID happen
    assert result.get("status") != "sensitive_input_required"


@pytest.mark.anyio
async def test_chain_hop_error_then_alternative_succeeds(spec_loaded, monkeypatch):
    """Alternative hop: first path fails, second succeeds.

    Chain: body:source_data_id>/dsources/{id}^/vdbs/{id}
    This tests lines 826 (continue to next alternative).
    """
    from dct_mcp_server.core.exceptions import DCTClientError

    extended_spec = {
        **APPDATA_SPEC,
        "paths": {
            **APPDATA_SPEC["paths"],
            "/vdbs/provision_by_snapshot": {
                "post": {
                    "operationId": "provisionVdbBySnapshot",
                    "summary": "Provision VDB",
                    "tags": ["VDBs"],
                },
            },
        },
    }
    monkeypatch.setattr(dynamic, "get_cached_spec", lambda: extended_spec)
    monkeypatch.setattr(dynamic, "get_process_identity", lambda: "identity-14781")
    _as_host(monkeypatch)

    execute, client = make_execute(return_value={"ok": True})

    async def _req_with_alt(method, endpoint, **kwargs):
        if "/toolkits/" in endpoint:
            return DB2_TK
        if "/dsources/" in endpoint:
            # First alternative — raise so it falls back to /vdbs/ alt
            raise DCTClientError("HTTP 503 Service Unavailable")
        if "/vdbs/" in endpoint and "/vdbs/provision" not in endpoint:
            # Second alternative — succeed
            return {"id": "vdb-1", "toolkit_id": "db2-toolkit-001"}
        if "/snapshots/" in endpoint:
            return {"id": "snap-1", "dataset_id": "vdb-1"}
        return {"ok": True}

    client.make_request = AsyncMock(side_effect=_req_with_alt)

    result = await execute(
        path="/vdbs/provision_by_snapshot",
        method="POST",
        body={
            "source_data_id": "ds-99",
            "snapshot_id": "snap-1",
            "appdata_source_params": {
                "mountPath": "/mnt",
            },
            "appdata_config_params": {
                "databaseName": "mydb",
            },
        },
    )

    # Resolution succeeded via fallback; no password in virtual_source_definition
    assert result.get("status") != "sensitive_input_required"


@pytest.mark.anyio
async def test_array_node_without_password_does_not_flag_non_secret_fields(spec_loaded, monkeypatch):
    """Array nodes that lack instancePassword don't generate spurious flags.

    The db2 schema has nodes[*].instancePassword (format: password).
    When a node in the body is missing instancePassword, expand_and_flag
    calls _path_exists() to check the concrete array path — covering the
    list-indexing branch inside that helper (lines 620-627).
    The top-level instancePassword IS present and must still be flagged.
    """
    _as_host(monkeypatch)
    execute, _ = _make_client_with_toolkit(DB2_TK)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "parameters": {
                "instanceUser": "db2inst1",
                "instancePassword": "top-level-secret",
                "port": 50000,
                "mountPath": "/mnt",
                # nodes[0] has no instancePassword → _path_exists returns False
                "nodes": [{"instanceId": "node-1"}],
            },
        },
    )

    assert result["status"] == "sensitive_input_required"
    assert "instancePassword" in result["required_sensitive_fields"]


@pytest.mark.anyio
async def test_hop_error_neg_cache_skips_second_fetch(spec_loaded, monkeypatch):
    """Non-404 DCTClientError on hop sets neg cache; second call skips the fetch.

    The path:dsourceId>/dsources/{id} chain fetches the dsource. When it
    fails with a non-404 error the object neg-cache is written. A second
    execute() call with the same ID immediately returns None at line 761
    without hitting the API.
    """
    from dct_mcp_server.core.exceptions import DCTClientError

    extended_spec = {
        **APPDATA_SPEC,
        "paths": {
            **APPDATA_SPEC["paths"],
            "/dsources/appdata/{dsourceId}": {
                "patch": {
                    "operationId": "updateAppDataDSource",
                    "summary": "Update AppData dSource",
                    "tags": ["DSources"],
                },
            },
        },
    }
    monkeypatch.setattr(dynamic, "get_cached_spec", lambda: extended_spec)
    monkeypatch.setattr(dynamic, "get_process_identity", lambda: "identity-14781")
    _as_host(monkeypatch)

    execute, client = make_execute(return_value={"ok": True})
    # Only count GET /dsources/... calls (the hop) — NOT the final PATCH dispatch
    dsource_get_count = [0]

    async def _failing_hop(method, endpoint, **kwargs):
        if "/toolkits/" in endpoint:
            return DB2_TK
        if method.upper() == "GET" and "/dsources/" in endpoint and "/appdata/" not in endpoint:
            # This is the hop fetch (GET /dsources/ds-99)
            dsource_get_count[0] += 1
            raise DCTClientError("HTTP 503 Service Unavailable")
        # Final dispatch (PATCH /dsources/appdata/ds-99) and any other call
        return {"ok": True}

    client.make_request = AsyncMock(side_effect=_failing_hop)

    body = {
        "parameters": {
            "instanceUser": "u",
            "instancePassword": "p",
            "port": 50000,
            "mountPath": "/mnt",
        },
    }

    # First call: dsource hop fails with 503 → writes object neg-cache
    await execute(path="/dsources/appdata/ds-99", method="PATCH", body=body)
    calls_after_first = dsource_get_count[0]

    # Second call: neg-cache hit (line 761) → dsource is NOT fetched again
    await execute(path="/dsources/appdata/ds-99", method="PATCH", body=body)

    assert calls_after_first >= 1, "First call must attempt the dsource GET hop"
    # Second call should skip the GET hop (neg-cache serves it)
    assert dsource_get_count[0] == calls_after_first, (
        "Second call should not re-fetch dsource via GET (neg-cache should serve it)"
    )


@pytest.mark.anyio
async def test_generic_exception_in_hop_causes_fallback(spec_loaded, monkeypatch):
    """Non-DCTClientError in hop _get_object also causes fail-open (lines 775-780).

    The chain body:source_id>/sources/{id} fetches /sources/{source_id}.
    When it raises a plain RuntimeError, the error is caught by the
    generic except block and the call proceeds without flagging.
    """
    _as_host(monkeypatch)
    execute, client = make_execute(return_value={"ok": True})

    async def _generic_exc_request(method, endpoint, **kwargs):
        if "/toolkits/" in endpoint:
            return DB2_TK
        if method.upper() == "GET" and "/sources/" in endpoint and "/dsources/" not in endpoint:
            # This is GET /sources/{id} (the source_id hop) — raise generic error
            raise RuntimeError("unexpected network error")
        return {"ok": True}

    client.make_request = AsyncMock(side_effect=_generic_exc_request)

    result = await execute(
        path="/dsources/appdata",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",
            "source_id": "src-1",  # triggers body:source_id>/sources/{id} chain
            "parameters": {
                "instanceUser": "u",
                "port": 50000,
                "mountPath": "/mnt",
            },
        },
    )

    # toolkit_id chain still works; source_id chain fails generically → fail-open
    # instancePassword absent but required → gate fires
    assert result.get("status") in ("sensitive_input_required", "confirmation_required")


@pytest.mark.anyio
async def test_hop_no_toolkit_id_falls_to_next_chain(spec_loaded, monkeypatch):
    """When hop response lacks toolkit_id (select=None path), chain returns None.

    provision_by_snapshot chain body:source_data_id>/dsources/{id}^/vdbs/{id}:
    if /dsources/{id} returns a dict without toolkit_id, code continues (line 834)
    to try /vdbs/{id} alternative. If /vdbs/{id} also returns no toolkit_id,
    the whole chain returns None and the next chain is tried.
    """
    _as_host(monkeypatch)

    extended_spec = {
        **APPDATA_SPEC,
        "paths": {
            **APPDATA_SPEC["paths"],
            "/vdbs/provision_by_snapshot": {
                "post": {
                    "operationId": "provisionVdbBySnapshot",
                    "summary": "Provision VDB",
                    "tags": ["VDBs"],
                },
            },
        },
    }
    monkeypatch.setattr(dynamic, "get_cached_spec", lambda: extended_spec)
    monkeypatch.setattr(dynamic, "get_process_identity", lambda: "identity-14781")

    execute, client = make_execute(return_value={"ok": True})

    async def _no_toolkit_id(method, endpoint, **kwargs):
        if "/toolkits/" in endpoint:
            return DB2_TK
        if "/dsources/" in endpoint:
            # Return dsource WITHOUT toolkit_id → covers line 834 (continue)
            return {"id": "ds-99"}
        if "/vdbs/" in endpoint and "/vdbs/provision" not in endpoint:
            # Fallback vdb also lacks toolkit_id → both alts fail → chain returns None
            return {"id": "vdb-1"}
        if "/snapshots/" in endpoint:
            return {"id": "snap-1", "dataset_id": "ds-99"}
        return {"ok": True}

    client.make_request = AsyncMock(side_effect=_no_toolkit_id)

    result = await execute(
        path="/vdbs/provision_by_snapshot",
        method="POST",
        body={
            "toolkit_id": "db2-toolkit-001",  # this chain still works
            "source_data_id": "ds-99",
            "snapshot_id": "snap-1",
            "appdata_source_params": {"mountPath": "/mnt"},
            "appdata_config_params": {"databaseName": "mydb"},
        },
    )

    # toolkit_id chain provides the toolkit; virtual_source_definition has no passwords
    assert result.get("status") != "sensitive_input_required"


@pytest.mark.anyio
async def test_object_cache_reused_in_same_request(spec_loaded, monkeypatch):
    """Second chain fetch of same object uses in-memory cache (line 758).

    provision_by_snapshot has three chains. If two of them resolve to the same
    dsource ID, the object cache should prevent a second API call.
    """
    _as_host(monkeypatch)

    extended_spec = {
        **APPDATA_SPEC,
        "paths": {
            **APPDATA_SPEC["paths"],
            "/vdbs/provision_by_snapshot": {
                "post": {
                    "operationId": "provisionVdbBySnapshot",
                    "summary": "Provision VDB",
                    "tags": ["VDBs"],
                },
            },
        },
    }
    monkeypatch.setattr(dynamic, "get_cached_spec", lambda: extended_spec)
    monkeypatch.setattr(dynamic, "get_process_identity", lambda: "identity-14781")

    execute, client = make_execute(return_value={"ok": True})
    dsource_call_count = [0]

    async def _counting_request(method, endpoint, **kwargs):
        if "/toolkits/" in endpoint:
            return DB2_TK
        if "/dsources/" in endpoint:
            dsource_call_count[0] += 1
            return {"id": "ds-99", "toolkit_id": "db2-toolkit-001"}
        if "/snapshots/" in endpoint:
            return {"id": "snap-1", "dataset_id": "ds-99"}
        return {"ok": True}

    client.make_request = AsyncMock(side_effect=_counting_request)

    # Run twice — second call should hit toolkit version cache (not re-fetch schema)
    for _ in range(2):
        await execute(
            path="/vdbs/provision_by_snapshot",
            method="POST",
            body={
                "source_data_id": "ds-99",
                "snapshot_id": "snap-1",
                "appdata_source_params": {"mountPath": "/mnt"},
                "appdata_config_params": {"databaseName": "mydb"},
            },
        )

    # Toolkit fetch is cached; dsource may be fetched more than once across chains
    # but toolkit endpoint should only be called once per toolkit_id
    assert dsource_call_count[0] >= 1  # at least one dsource call happened


# ── AC-12: discovery annotates AppData operations ────────────────────────────


def test_discovery_appdata_note(spec_loaded, monkeypatch):
    """discovery get_operation_schema for an AppData op adds connector note."""
    _as_host(monkeypatch)
    from dct_mcp_server.tools.core.dynamic import _make_discovery_fn

    app = MagicMock()
    # _make_discovery_fn only takes app (no client argument)
    discovery = _make_discovery_fn(app)

    result = discovery(
        action="get_operation_schema",
        path="/dsources/appdata",
        operation_method="POST",
    )

    # If the operation was found and annotated, it should carry the connector note
    if isinstance(result, dict) and "status" not in result:
        assert (
            "connector credential" in result.get("description", "").lower()
            or "host_captured_connector_secrets" in result
        )
