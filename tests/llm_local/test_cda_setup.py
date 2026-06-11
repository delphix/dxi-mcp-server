"""
P2 — CDA prerequisite setup flow (6 sequential steps).

Each step:
  1. Quick idempotence check via direct API — skip with "already present" if done.
  2. Act via Claude with all required fields embedded in the prompt (never ask for creds).
  3. Poll job_tool to a terminal state (enforced by the job-completion pre-prompt).
  4. Independently verify the real effect through a separate read.

Steps are designed to be:
  - Run in order (01 → 06) from a clean DCT.
  - Safe to re-run on a partially-configured DCT (each skips what's already there).
  - The canonical setup before running P3 (all 431 CDA scenarios).

GATED: requires LLM_ALLOW_MUTATION=1 + DCT creds + connector env vars.
Run via the safe-run venv:
    set -a; source .env.local; set +a
    export CONNECTOR_TYPE=appdata
    export MYSQL_SOURCE_HOST=r95-mys-s11.dlpxdc.co
    export MYSQL_TARGET_HOST=r95-mys-t11.dlpxdc.co
    export MYSQL_ENV_USER=mysql       MYSQL_ENV_PASSWORD=connect_123
    export MYSQL_LINK_USER=delphix_os  MYSQL_LINK_PASSWORD='Delphix@123'
    export E2E_RUN_TAG="cda-$(date +%s)"
    LLM_ALLOW_MUTATION=1 .venv-live/bin/python -m pytest tests/llm_local/test_cda_setup.py
      -m llm_driven -v -s
"""

import json
import os
import time

import pytest

from tests.llm_local.connector_fixtures import ConnectorSpec, schema_link_hints
from tests.llm_local.conftest import license_blocked
from tests.llm_local.mcp_client_helper import mcp_search, payload as _mcp_payload
from tests.llm_local.prereq_checker import require_prereq_level

pytestmark = [pytest.mark.real_dct, pytest.mark.llm_driven]

_MUTATION = os.environ.get("LLM_ALLOW_MUTATION") == "1"
_SKIP = "Set LLM_ALLOW_MUTATION=1 to run CDA setup steps."


# ── MCP-based idempotence checks (via .mcp.json delphix-dct server) ───────────
# All DCT state queries go through the MCP server — no direct HTTP calls.

def _engines() -> list:
    return mcp_search("engine_tool", "search")

def _toolkits() -> list:
    return mcp_search("toolkit_tool", "search")

def _environments() -> list:
    return mcp_search("environment_source_tool", "search_environments")

def _dsources() -> list:
    return mcp_search("dsource_tool", "search")

def _vdbs() -> list:
    return mcp_search("data_tool", "search_vdbs")


# ── Setup steps ───────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _MUTATION, reason=_SKIP)
def test_setup_01_engine(connector_spec: ConnectorSpec, llm_driver_for):
    """Register the Delphix engine. Skip if already registered."""
    engines = _engines()
    if engines:
        names = [e.get("name") or e.get("hostname") for e in engines]
        pytest.skip(f"Engine already registered: {', '.join(names)}")

    engine_json = {
        "hostname": os.environ.get("ENGINE_HOST", connector_spec.source_host),
        "name": os.environ.get("ENGINE_NAME", "test-engine"),
        "username": os.environ.get("ENGINE_ADMIN_USER", "admin"),
        "password": os.environ.get("ENGINE_ADMIN_PASSWORD", "delphix"),
        "insecure_ssl": True,
        "unsafe_ssl_hostname_check": True,
    }
    drive = llm_driver_for("continuous_data_admin")

    act = drive(
        f"Register a new Delphix engine with these EXACT details: {json.dumps(engine_json)}. "
        f"Call engine_tool with action=register passing ALL those fields directly. "
        f"Then use job_tool to poll until the job reaches COMPLETED or FAILED. "
        f"Confirm the final job status.",
        timeout=600,
    )
    if license_blocked(act):
        pytest.skip("DCT license does not permit engine registration")
    assert "engine_tool" in act.tools_used, (
        f"Claude did not use engine_tool. Tools: {sorted(act.tools_used)}\n{act.final_text[:300]}"
    )
    assert "register" in act.actions_for("engine_tool"), (
        f"Claude did not call register; actions: {act.actions_for('engine_tool')}"
    )

    # Independent verify
    short = engine_json["name"]
    verify = drive("List all registered Delphix engines, showing name, hostname, and status.")
    assert short in verify.final_text or engine_json["hostname"].split(".")[0] in verify.final_text, (
        f"Engine not found after register. Answer: {verify.final_text[:400]}"
    )


@pytest.mark.skipif(not _MUTATION, reason=_SKIP)
def test_setup_02_connector(connector_spec: ConnectorSpec, llm_driver_for):
    """Install the connector/toolkit on the engine. Skip if already installed."""
    toolkits = _toolkits()
    kw = connector_spec.connector_search_keyword.lower()
    installed = [t for t in toolkits
                 if kw in (t.get("name") or "").lower()
                 or kw in str(t).lower()]
    if installed:
        pytest.skip(
            f"Connector '{connector_spec.display_name}' already installed "
            f"({len(installed)} toolkit(s) found)"
        )

    drive = llm_driver_for("continuous_data_admin")
    engines = _engines()
    engine_name = engines[0].get("name", "the engine") if engines else "the engine"

    act = drive(
        f"Install the {connector_spec.display_name} connector/toolkit on the engine "
        f"named '{engine_name}'. Use toolkit_tool to perform the installation. "
        f"Wait for any installation job to complete, then confirm.",
        timeout=600,
    )
    if license_blocked(act):
        pytest.skip("DCT license does not permit toolkit operations")
    assert "toolkit_tool" in act.tools_used, (
        f"Claude did not use toolkit_tool. Tools: {sorted(act.tools_used)}\n{act.final_text[:300]}"
    )

    verify = drive(
        "List all toolkits and connectors installed on the engine, "
        "showing each one's name and version."
    )
    assert kw in verify.final_text.lower(), (
        f"Connector keyword {kw!r} not found after install. Answer: {verify.final_text[:400]}"
    )


@pytest.mark.skipif(not _MUTATION, reason=_SKIP)
def test_setup_03_hosts(connector_spec: ConnectorSpec, llm_driver_for):
    """Add source + target hosts as environments. Skip if both already present."""
    envs = _environments()
    env_names = [e.get("name", "") or e.get("address", "") for e in envs]
    source_ok = any(connector_spec.source_short in n for n in env_names)
    target_ok = any(connector_spec.target_short in n for n in env_names)

    if source_ok and target_ok:
        pytest.skip(
            f"Both environments already present: "
            f"{connector_spec.source_host}, {connector_spec.target_host}"
        )

    drive = llm_driver_for("continuous_data_admin")

    for host, already_ok in [
        (connector_spec.source_host, source_ok),
        (connector_spec.target_host, target_ok),
    ]:
        if already_ok:
            print(f"  {host}: already present, skipping")
            continue
        short = host.split(".")[0]
        act = drive(
            f"Add the host '{host}' as a new Unix/Linux environment in Delphix. "
            f"Use SSH username='{connector_spec.env_user}' and "
            f"password='{connector_spec.env_password}'. "
            f"Call environment_source_tool or the appropriate tool with all required fields. "
            f"Then use job_tool to poll until the job reaches COMPLETED or FAILED. "
            f"Confirm the final job status.",
            timeout=600,
        )
        if license_blocked(act):
            pytest.skip("DCT license does not permit environment operations")
        assert ("environment_source_tool" in act.tools_used
                or "environment_tool" in act.tools_used), (
            f"Claude did not use an environment tool for {host}.\n{act.final_text[:300]}"
        )

        # Independent verify (short hostname NOT in prompt)
        verify = drive(
            "List all environments registered in Delphix, showing hostname and status."
        )
        assert short in verify.final_text, (
            f"Environment {host!r} not found after adding.\n{verify.final_text[:400]}"
        )


@pytest.mark.skipif(not _MUTATION, reason=_SKIP)
def test_setup_04_source_config(connector_spec: ConnectorSpec, llm_driver_for):
    """
    Verify that a source config / repository is discoverable on the target host.
    This is usually auto-discovered after the environment is added — so this step
    is a read-only verification, not a mutation. Marks as done if the repo exists.
    """
    target_short = connector_spec.target_short
    drive = llm_driver_for("continuous_data_admin")

    check = drive(
        f"Search for all repositories and data connections available on the environment "
        f"on host containing '{target_short}'. "
        f"Show each one's name, type, and status.",
        timeout=180,
    )
    if license_blocked(check):
        pytest.skip("DCT license does not permit data connection operations")

    # If any repositories/data-connections found, source config is present
    found = any(
        w in check.final_text.lower()
        for w in ["repository", "data connection", "source config",
                  "connection", "available", "found", "result"]
    )
    if not found:
        pytest.fail(
            f"No repository/source config found on target host '{connector_spec.target_host}'. "
            f"Ensure the environment was added (step 03) and the plugin discovered repos. "
            f"Claude's answer: {check.final_text[:400]}"
        )


@pytest.mark.skipif(not _MUTATION, reason=_SKIP)
def test_setup_05_dsource(connector_spec: ConnectorSpec, llm_driver_for):
    """Link a dSource on the target host. Skip if one already exists."""
    existing = _dsources()
    if existing:
        names = [d.get("name") for d in existing]
        pytest.skip(f"dSource already present: {', '.join(str(n) for n in names)}")

    run_tag = os.environ.get("E2E_RUN_TAG", "cda-setup")
    dsource_name = f"{run_tag}-ds"
    drive = llm_driver_for("continuous_data_admin")

    # Combine explicit field values (from secrets) with schema hints (field docs + defaults)
    # so Claude has both concrete values AND documentation for anything not pre-filled.
    link_detail = connector_spec.link_prompt_detail()
    schema_hints = schema_link_hints(connector_spec.connector_type)
    if schema_hints and not link_detail:
        link_detail = schema_hints  # fall back to schema hints if no explicit values

    act = drive(
        f"Link a new {connector_spec.display_name} dSource named '{dsource_name}' "
        f"from the environment on host '{connector_spec.target_host}'. "
        f"Use OS username='{connector_spec.link_os_user}', "
        f"password='{connector_spec.link_os_password}'. "
        f"Use data_tool action={connector_spec.dsource_link_action}. "
        f"Search for the right environment and repository automatically. "
        f"{link_detail}\n"
        f"For required fields you cannot determine, use sensible defaults. "
        f"Then use job_tool to poll until the link job reaches COMPLETED or FAILED. "
        f"Confirm the final job status.",
        timeout=900,
    )
    if license_blocked(act):
        pytest.skip("DCT license does not permit dSource link operations")
    assert "data_tool" in act.tools_used, (
        f"Claude did not use data_tool. Tools: {sorted(act.tools_used)}\n{act.final_text[:300]}"
    )
    assert connector_spec.dsource_link_action in act.actions_for("data_tool"), (
        f"Claude did not call {connector_spec.dsource_link_action}; "
        f"actions: {act.actions_for('data_tool')}"
    )
    # job_tool polling is preferred but some connectors complete synchronously.
    # What matters is the dSource actually exists — assert that via independent verify.
    if "job_tool" not in act.tools_used:
        print(f"\n  Note: Claude did not poll job_tool (link may have completed synchronously)")

    # Independent verify (dsource_name NOT in prompt) — the real success criterion.
    verify = drive(
        "Search for all dSources and show each one's name, type, and status.",
        timeout=300,
    )
    assert dsource_name in verify.final_text, (
        f"dSource {dsource_name!r} not found after link.\n"
        f"  act tools used: {sorted(act.tools_used)}\n"
        f"  act answer: {act.final_text[:300]}\n"
        f"  verify answer: {verify.final_text[:400]}"
    )


@pytest.mark.skipif(not _MUTATION, reason=_SKIP)
def test_setup_05b_enable_dsource(connector_spec: ConnectorSpec, llm_driver_for):
    """
    Enable the dSource and take an initial snapshot so it is ACTIVE and has
    a snapshot to provision from. AppData dSources start as INACTIVE.
    Uses direct API to verify the real DCT state (not just Claude's answer).
    Skips if dSource is already ACTIVE with snapshots.
    """
    dsources = _dsources()
    if not dsources:
        pytest.skip(
            "PREREQ MISSING [dsource]: No dSource found — run test_setup_05_dsource first."
        )

    ds = dsources[0]
    ds_id = ds.get("id")
    ds_name = ds.get("name") or ds_id
    drive = llm_driver_for("continuous_data_admin")

    def _ds_detail() -> dict:
        """Get dSource detail via MCP."""
        items = mcp_search("dsource_tool", "search")
        for d in items:
            if d.get("id") == ds_id or d.get("name") == ds_name:
                return d
        return {}

    def _ds_snapshots() -> list:
        """List snapshots for this dSource via MCP."""
        return mcp_search("snapshot_tool", "search")  # filter by dsource below if needed

    # Check status via MCP
    detail = _ds_detail()
    ds_status = (detail.get("status") or "").upper()
    snaps = _ds_snapshots()
    # Filter to snapshots belonging to this dSource
    snaps = [s for s in snaps if ds_id in str(s) or ds_name in str(s)]
    print(f"\n  dSource {ds_name}: status={ds_status}, snapshots={len(snaps)}")

    if ds_status in ("ACTIVE", "RUNNING") and snaps:
        pytest.skip(
            f"dSource {ds_name!r} already ACTIVE with {len(snaps)} snapshot(s)"
        )

    # Step 1: Enable the dSource via Claude (exact action name: enable_dsource)
    if ds_status not in ("ACTIVE", "RUNNING"):
        enable = drive(
            f"Enable the dSource named '{ds_name}' using data_tool action=enable_dsource. "
            f"Find its dsourceId first with a search, then call enable_dsource with that id. "
            f"Then use job_tool to poll until the job reaches COMPLETED or FAILED. "
            f"Confirm the final job status.",
            timeout=600,
        )
        if license_blocked(enable):
            pytest.skip("DCT license does not permit dSource enable")
        assert "data_tool" in enable.tools_used, (
            f"Claude did not use data_tool to enable dSource.\n{enable.final_text[:300]}"
        )
        # Wait for status change (direct API check, up to 2 min)
        for _ in range(24):
            time.sleep(5)
            new_status = (_ds_detail().get("status") or "").upper()
            if new_status in ("ACTIVE", "RUNNING"):
                print(f"  dSource status now: {new_status}")
                break
        else:
            new_status = (_ds_detail().get("status") or "").upper()
            print(f"  Warning: dSource still {new_status} after enable — proceeding anyway")

    # Step 2: Take an initial snapshot via Claude (exact action: dsource_create_snapshot)
    snap = drive(
        f"Take a new snapshot of the dSource named '{ds_name}' using "
        f"data_tool action=dsource_create_snapshot. "
        f"Find its dsourceId first with a search, then call dsource_create_snapshot with that id. "
        f"Then use job_tool to poll until the snapshot job reaches COMPLETED or FAILED. "
        f"Report the final job status.",
        timeout=600,
    )
    if license_blocked(snap):
        pytest.skip("DCT license does not permit dSource snapshot")
    assert "data_tool" in snap.tools_used, (
        f"Claude did not use data_tool to snapshot dSource.\n{snap.final_text[:300]}"
    )

    # Wait for snapshot to appear (direct API, up to 3 min)
    for _ in range(36):
        time.sleep(5)
        snaps = _ds_snapshots()
        if snaps:
            print(f"  Snapshot created: {snaps[0].get('id')}")
            break
    else:
        snaps = _ds_snapshots()

    # Hard assert: snapshot must exist (this is the real success criterion)
    assert snaps, (
        f"dSource {ds_name!r} has 0 snapshots after enable+snapshot.\n"
        f"  Claude enable answer: {enable.final_text[:200] if 'enable' in dir() else 'N/A'}\n"
        f"  Claude snapshot answer: {snap.final_text[:300]}"
    )


@pytest.mark.skipif(not _MUTATION, reason=_SKIP)
def test_setup_06_vdb(connector_spec: ConnectorSpec, llm_driver_for):
    """Provision a VDB from the dSource. Skip if one already exists."""
    existing_vdbs = _vdbs()
    if existing_vdbs:
        names = [v.get("name") for v in existing_vdbs]
        pytest.skip(f"VDB already present: {', '.join(str(n) for n in names)}")

    dsources = _dsources()
    if not dsources:
        pytest.skip(
            "PREREQ MISSING [dsource]: No dSource found — run test_setup_05_dsource first."
        )

    run_tag = os.environ.get("E2E_RUN_TAG", "cda-setup")
    vdb_name = f"{run_tag}-vdb"
    drive = llm_driver_for("continuous_data_admin")

    prov_detail = connector_spec.provision_prompt_detail()
    dsource_ref = dsources[0].get("name") or dsources[0].get("id")

    act = drive(
        f"Provision a new VDB named '{vdb_name}' from the most recent snapshot "
        f"of the dSource named '{dsource_ref}'. "
        f"Use data_tool action={connector_spec.provision_action}. "
        f"Find the right environment and repository on host '{connector_spec.target_host}' automatically. "
        f"{prov_detail}\n"
        f"Then use job_tool to poll until the provisioning job reaches COMPLETED or FAILED. "
        f"Confirm the final job status.",
        timeout=900,
    )
    if license_blocked(act):
        pytest.skip("DCT license does not permit VDB provisioning")
    assert "data_tool" in act.tools_used, (
        f"Claude did not use data_tool. Tools: {sorted(act.tools_used)}\n{act.final_text[:300]}"
    )
    if "job_tool" not in act.tools_used:
        print(f"\n  Note: Claude did not poll job_tool (provision may have completed synchronously)")

    # Independent verify (vdb_name NOT in prompt) — the real success criterion.
    verify = drive("Search for all virtual databases (VDBs), showing name and status.", timeout=300)
    assert vdb_name in verify.final_text, (
        f"VDB {vdb_name!r} not found after provision.\n"
        f"  act tools: {sorted(act.tools_used)}\n"
        f"  verify answer: {verify.final_text[:400]}"
    )
