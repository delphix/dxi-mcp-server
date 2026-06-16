"""
Layer 5 — MySQL full workflow: register engine → environments → source config
          → dSource (Staging Push) → VDB → verify → cleanup.

Each test is one step in the chain. Run them in order:

    CONNECTOR_TYPE=mysql LLM_ALLOW_MUTATION=1 \\
      DCT_BASE_URL=https://<dct> DCT_API_KEY=<key> \\
      pytest tests/llm_local/test_mysql_full_workflow.py -v -s

GATED: every test skips unless LLM_ALLOW_MUTATION=1 AND secrets are present.
Run ONLY against a DISPOSABLE / CLONED DCT — this workflow creates and deletes
real objects (engine registration, environments, source config, dSource, VDB).

Secrets come from tests/fixtures/connectors/.secrets.yaml or
DCT_ENGINE_* / DCT_CONNECTOR_MYSQL_* env vars (CI).

Workflow summary:
  1. test_ai_registers_engine           — register Delphix Engine with DCT
  2. test_ai_adds_mysql_environments    — add source + target as environments
  3. test_ai_creates_source_config      — AppData source config on target
  4. test_ai_links_mysql_dsource        — link dSource, Staging Push ingestion
  5. test_ai_provisions_mysql_vdb       — provision VDB from latest snapshot
  6. test_ai_cleanup_mysql_workflow     — teardown in reverse order
"""

from __future__ import annotations

import json
import os

import pytest

from tests.llm_local.conftest import license_blocked, DriverResult
from tests.llm_local.connector_fixtures import ConnectorSpec, EngineSpec


def _l5(label: str, prompt: str, result: DriverResult) -> None:
    """Print a structured L5_DETAIL line captured by pytest-json-report stdout."""
    print(
        "\nL5_DETAIL:"
        + json.dumps({
            "label": label,
            "prompt": prompt[:600],
            "tools_used": sorted(result.tools_used),
            "tool_calls": [
                {"tool": c.name, "action": c.input.get("action"), "input_keys": sorted(c.input.keys())}
                for c in result.tool_calls
            ],
            "final_text": result.final_text[:500],
            "returncode": result.returncode,
        })
    )

pytestmark = [pytest.mark.real_dct, pytest.mark.llm_driven]

_MUTATION = os.environ.get("LLM_ALLOW_MUTATION") == "1"


# ── Gate helpers ──────────────────────────────────────────────────────────────

def _require_mutation():
    if not _MUTATION:
        pytest.skip(
            "Set LLM_ALLOW_MUTATION=1 to run full MySQL workflow tests. "
            "Run ONLY against a DISPOSABLE DCT."
        )


def _require_engine(spec: EngineSpec):
    if not spec.hostname:
        pytest.skip(
            "Engine hostname not set — add 'engine.hostname' to "
            "tests/fixtures/connectors/.secrets.yaml"
        )


def _require_connector(spec: ConnectorSpec):
    if not spec.target_host:
        pytest.skip(
            f"No target_host for connector '{spec.connector_type}'. "
            f"Set DCT_CONNECTOR_{spec.connector_type.upper()}_TARGET_HOST "
            f"or add it to .secrets.yaml."
        )
    if not spec.env_password or not spec.link_password:
        pytest.skip(
            f"Missing credentials for connector '{spec.connector_type}'. "
            f"Add env_password and link_password to .secrets.yaml."
        )


# ── Step 1 — Register engine ──────────────────────────────────────────────────

def test_ai_registers_engine(engine_spec: EngineSpec, llm_driver_for):
    """Register the Delphix Engine with DCT. Skip if already registered."""
    _require_mutation()
    _require_engine(engine_spec)

    drive = llm_driver_for("continuous_data_admin")

    act_prompt = (
        f"Register a Delphix Engine with DCT using engine_tool action=register. "
        f"Use: name='{engine_spec.name}', hostname='{engine_spec.hostname}', "
        f"username='{engine_spec.username}', password='{engine_spec.password}', "
        f"insecure_ssl={str(engine_spec.insecure_ssl).lower()}. "
        f"If an engine with hostname '{engine_spec.hostname}' is already registered "
        f"(search first), skip registration and report it as already present."
    )
    act = drive(act_prompt, timeout=120)
    if license_blocked(act):
        pytest.skip("DCT license does not permit engine registration")
    _l5("act:register_engine", act_prompt, act)
    assert "engine_tool" in act.tools_used, (
        f"Claude did not use engine_tool.\n{act.final_text[:400]}"
    )

    verify_prompt = "List all registered engines showing their names and hostnames."
    verify = drive(verify_prompt)
    _l5("verify:list_engines", verify_prompt, verify)
    assert engine_spec.hostname in verify.final_text, (
        f"Engine '{engine_spec.hostname}' not found after registration.\n"
        f"{verify.final_text[:400]}"
    )


# ── Step 2 — Add source + target environments ─────────────────────────────────

def test_ai_adds_mysql_environments(
    engine_spec: EngineSpec,
    connector_spec: ConnectorSpec,
    llm_driver_for,
):
    """Add source and target MySQL hosts as Unix environments on the engine."""
    _require_mutation()
    _require_engine(engine_spec)
    _require_connector(connector_spec)

    drive = llm_driver_for("continuous_data_admin")
    hosts = [connector_spec.source_host, connector_spec.target_host]

    for host in hosts:
        short = host.split(".")[0]

        act = drive(
            f"Add the host '{host}' as a new Unix/Linux environment in Delphix. "
            f"Find the engine with hostname '{engine_spec.hostname}' to get its engine_id. "
            f"Use OS username='{connector_spec.env_user}', "
            f"password='{connector_spec.env_password}', "
            f"toolkit_path='{connector_spec.toolkit_path}'. "
            f"If an environment for '{host}' already exists, skip and report it. "
            f"Otherwise use environment_source_tool or environment_tool to create it. "
            f"Poll job_tool until the job reaches COMPLETED or FAILED.",
            timeout=600,
        )
        if license_blocked(act):
            pytest.skip("DCT license does not permit environment operations")
        assert (
            "environment_source_tool" in act.tools_used
            or "environment_tool" in act.tools_used
        ), (
            f"Claude did not use an environment tool for {host}.\n"
            f"{act.final_text[:300]}"
        )

        # Independent verify — do not mention short hostname in the prompt
        verify = drive(
            "List all environments registered in Delphix showing hostname and status."
        )
        assert short in verify.final_text, (
            f"Environment '{host}' not found after adding.\n"
            f"{verify.final_text[:400]}"
        )


# ── Step 3 — Create source config on target host ──────────────────────────────

def test_ai_creates_source_config(connector_spec: ConnectorSpec, llm_driver_for):
    """Create an AppData source config on the target environment."""
    _require_mutation()
    _require_connector(connector_spec)

    drive = llm_driver_for("continuous_data_admin")
    sc_name = connector_spec.source_config_name

    act = drive(
        f"Create an AppData source config named '{sc_name}' on the environment "
        f"'{connector_spec.target_host}' using data_tool action=create_appdata_source. "
        f"Search for the environment_id from '{connector_spec.target_host}' and its "
        f"repository_id (MySQL/AppData plugin repository) automatically. "
        f"Pass these plugin parameters: "
        f"dataDir='{connector_spec.data_dir}', "
        f"port={connector_spec.source_port}, "
        f"baseDir='{connector_spec.base_dir}'. "
        f"Set environment_user='{connector_spec.env_user}'. "
        f"If a source config named '{sc_name}' already exists, skip and report it. "
        f"Wait for any job to complete before reporting.",
        timeout=300,
    )
    if license_blocked(act):
        pytest.skip("DCT license does not permit source config creation")
    assert "data_tool" in act.tools_used, (
        f"Claude did not use data_tool.\n{act.final_text[:300]}"
    )

    # Independent verify
    verify = drive(
        "Search for all sources and list their names and environments."
    )
    assert sc_name in verify.final_text, (
        f"Source config '{sc_name}' not found after creation.\n"
        f"{verify.final_text[:400]}"
    )


# ── Step 4 — Link dSource (Staging Push) ─────────────────────────────────────

def test_ai_links_mysql_dsource(connector_spec: ConnectorSpec, llm_driver_for):
    """Link a MySQL dSource using Staging Push ingestion (AppDataStaged)."""
    _require_mutation()
    _require_connector(connector_spec)

    drive = llm_driver_for("continuous_data_admin")
    run_tag = os.environ.get("E2E_RUN_TAG", "e2e-local")
    dsource_name = f"{run_tag}-{connector_spec.connector_type}-ds"

    link_detail = connector_spec.link_prompt_detail()

    act = drive(
        f"Link a new {connector_spec.display_name} dSource named '{dsource_name}' "
        f"using source config '{connector_spec.source_config_name}' on environment "
        f"'{connector_spec.target_host}'. "
        f"Use data_tool action={connector_spec.dsource_link_action} with "
        f"link_type=AppDataStaged (Staging Push). "
        f"Search for the source_id from source config '{connector_spec.source_config_name}' "
        f"and the staging_environment_id from environment '{connector_spec.target_host}'. "
        f"Set environment_user='{connector_spec.env_user}'. "
        f"{link_detail}\n"
        f"For any fields not listed, call dsource_link_appdata_defaults first to get defaults. "
        f"Poll job_tool until the link job reaches COMPLETED or FAILED. "
        f"Report the final job status.",
        timeout=900,
    )
    if license_blocked(act):
        pytest.skip(
            f"DCT license does not permit {connector_spec.dsource_link_action} operations"
        )
    assert "data_tool" in act.tools_used, (
        f"Claude did not use data_tool. Tools used: {sorted(act.tools_used)}\n"
        f"{act.final_text[:300]}"
    )
    assert connector_spec.dsource_link_action in act.actions_for("data_tool"), (
        f"Claude did not call {connector_spec.dsource_link_action}. "
        f"Actions on data_tool: {act.actions_for('data_tool')}"
    )

    # Independent verify — do not mention dsource_name in the prompt
    verify = drive(
        "Search for all dSources and show each one's name, type, and status."
    )
    assert dsource_name in verify.final_text, (
        f"dSource '{dsource_name}' not found after link.\n"
        f"{verify.final_text[:400]}"
    )


# ── Step 5 — Provision VDB ────────────────────────────────────────────────────

def test_ai_provisions_mysql_vdb(connector_spec: ConnectorSpec, llm_driver_for):
    """Provision a MySQL VDB from the latest dSource snapshot."""
    _require_mutation()
    _require_connector(connector_spec)

    drive = llm_driver_for("continuous_data_admin")
    run_tag = os.environ.get("E2E_RUN_TAG", "e2e-local")
    dsource_name = f"{run_tag}-{connector_spec.connector_type}-ds"
    vdb_name = f"{run_tag}-{connector_spec.vdb_name}"

    provision_detail = connector_spec.provision_prompt_detail()

    act = drive(
        f"Provision a {connector_spec.display_name} VDB named '{vdb_name}' "
        f"from the latest snapshot of dSource '{dsource_name}' "
        f"onto environment '{connector_spec.target_host}'. "
        f"Use data_tool action={connector_spec.provision_action}. "
        f"Search for the source_data_id (dSource id) and target_group_id automatically. "
        f"Use environment '{connector_spec.target_host}' with user '{connector_spec.env_user}'. "
        f"{provision_detail}\n"
        f"For any fields not listed, call provision_by_snapshot_defaults first. "
        f"Poll job_tool until the provision job reaches COMPLETED or FAILED. "
        f"Report the final job status.",
        timeout=900,
    )
    if license_blocked(act):
        pytest.skip(
            f"DCT license does not permit {connector_spec.provision_action} operations"
        )
    assert "data_tool" in act.tools_used, (
        f"Claude did not use data_tool. Tools used: {sorted(act.tools_used)}\n"
        f"{act.final_text[:300]}"
    )
    assert connector_spec.provision_action in act.actions_for("data_tool"), (
        f"Claude did not call {connector_spec.provision_action}. "
        f"Actions on data_tool: {act.actions_for('data_tool')}"
    )

    # Independent verify — do not mention vdb_name in the prompt
    verify = drive(
        "Search for all VDBs and show each one's name, type, and status."
    )
    assert vdb_name in verify.final_text, (
        f"VDB '{vdb_name}' not found after provisioning.\n"
        f"{verify.final_text[:400]}"
    )


# ── Step 6 — Cleanup ─────────────────────────────────────────────────────────

def test_ai_cleanup_mysql_workflow(connector_spec: ConnectorSpec, llm_driver_for):
    """
    Tear down in reverse order: VDB → dSource → source config → environments.
    Always runs (even if earlier steps failed) so DCT is left clean.
    Each deletion is best-effort — a missing object is not a failure.
    """
    _require_mutation()

    drive = llm_driver_for("continuous_data_admin")
    run_tag = os.environ.get("E2E_RUN_TAG", "e2e-local")
    dsource_name = f"{run_tag}-{connector_spec.connector_type}-ds"
    vdb_name = f"{run_tag}-{connector_spec.vdb_name}"

    # Delete VDB
    drive(
        f"Delete the VDB named '{vdb_name}' if it exists. "
        f"If it does not exist, that is fine — do not error. "
        f"Poll job_tool until the deletion job reaches COMPLETED or FAILED.",
        timeout=300,
    )

    # Delete dSource
    drive(
        f"Delete the dSource named '{dsource_name}' if it exists. "
        f"If it does not exist, that is fine — do not error. "
        f"Poll job_tool until the deletion job reaches COMPLETED or FAILED.",
        timeout=300,
    )

    # Delete source config
    drive(
        f"Delete the source config named '{connector_spec.source_config_name}' "
        f"if it exists. If it does not exist, that is fine.",
        timeout=120,
    )

    # Delete environments (target first — it hosts the staging/VDB)
    for host in [connector_spec.target_host, connector_spec.source_host]:
        if not host:
            continue
        drive(
            f"Delete the environment with hostname '{host}' if it exists. "
            f"If it does not exist, that is fine. "
            f"Poll job_tool until the deletion job completes.",
            timeout=300,
        )
