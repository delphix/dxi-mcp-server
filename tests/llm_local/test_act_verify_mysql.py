"""
Layer 5 — Connector act → verify scenarios: add environments + link dSource.

Works for ANY connector type defined in tests/fixtures/connectors/schema.yaml.
Credentials and topology come from tests/fixtures/connectors/.secrets.yaml (local)
or DCT_CONNECTOR_<TYPE>_<FIELD> env vars (CI). Select the connector with:

    CONNECTOR_TYPE=mysql   (default)
    CONNECTOR_TYPE=db2
    CONNECTOR_TYPE=postgresql
    ...

Flow:
    test_ai_adds_both_environments          — adds source + target hosts as environments
    test_ai_links_dsource_and_verifies      — links dSource on target, verifies, cleanup

GATED: skipped unless LLM_ALLOW_MUTATION=1 AND connector secrets are present.
Run only against a DISPOSABLE / CLONED DCT.
"""

import os

import pytest

from tests.llm_local.conftest import license_blocked
from tests.llm_local.connector_fixtures import ConnectorSpec, schema_link_hints

pytestmark = [pytest.mark.real_dct, pytest.mark.llm_driven]

_MUTATION = os.environ.get("LLM_ALLOW_MUTATION") == "1"


def _skip_reason(spec: ConnectorSpec) -> str | None:
    """Returns a skip reason if the connector isn't runnable, else None."""
    if not _MUTATION:
        return "Set LLM_ALLOW_MUTATION=1 to run connector act→verify tests."
    if not spec.target_host:
        return (
            f"No target_host for connector '{spec.connector_type}'. "
            f"Set DCT_CONNECTOR_{spec.connector_type.upper()}_TARGET_HOST or "
            f"add it to tests/fixtures/connectors/.secrets.yaml."
        )
    if not spec.env_password or not spec.link_password:
        return (
            f"Missing credentials for connector '{spec.connector_type}'. "
            f"Set DCT_CONNECTOR_{spec.connector_type.upper()}_ENV_PASSWORD and "
            f"LINK_PASSWORD, or add them to .secrets.yaml."
        )
    return None


@pytest.mark.asyncio
def test_ai_adds_both_environments(connector_spec: ConnectorSpec, llm_driver_for):
    """
    Add source + target hosts as Delphix environments.
    Works for any connector type — topology comes from connector_spec.
    """
    reason = _skip_reason(connector_spec)
    if reason:
        pytest.skip(reason)

    drive = llm_driver_for("continuous_data_admin")
    hosts = [h for h in [connector_spec.source_host, connector_spec.target_host] if h]

    for host in hosts:
        short = host.split(".")[0]

        act = drive(
            f"Add the host '{host}' as a new Unix/Linux environment in Delphix. "
            f"Use SSH username='{connector_spec.env_user}' and "
            f"password='{connector_spec.env_password}'. "
            f"Call environment_source_tool with all required fields. "
            f"Then poll job_tool until the job reaches COMPLETED or FAILED. "
            f"Confirm the final job status.",
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

        # Independent verify (short hostname NOT in prompt)
        verify = drive(
            "List all environments registered in Delphix, showing hostname and status."
        )
        assert short in verify.final_text, (
            f"Environment {host!r} not found after adding.\n"
            f"{verify.final_text[:400]}"
        )


@pytest.mark.asyncio
def test_ai_links_dsource_and_verifies(connector_spec: ConnectorSpec, llm_driver_for):
    """
    Link a dSource on the target host using the connector-specific parameters
    from the schema + secrets. Works for MySQL, DB2, PostgreSQL etc.

    act → wait for job → independent verify → cleanup
    """
    reason = _skip_reason(connector_spec)
    if reason:
        pytest.skip(reason)

    drive = llm_driver_for("continuous_data_admin")
    run_tag = os.environ.get("E2E_RUN_TAG", "e2e-local")
    dsource_name = f"{run_tag}-{connector_spec.connector_type}-ds"

    # Build prompt: explicit fields from secrets + schema hints for undetermined ones
    link_detail = connector_spec.link_prompt_detail()
    if not link_detail:
        link_detail = schema_link_hints(connector_spec.connector_type)

    act = drive(
        f"Link a new {connector_spec.display_name} dSource named '{dsource_name}' "
        f"from the environment on host '{connector_spec.target_host}'. "
        f"OS username: '{connector_spec.link_user}', password: '{connector_spec.link_password}'. "
        f"Use data_tool action={connector_spec.dsource_link_action}. "
        f"Search for the right environment and repository automatically. "
        f"{link_detail}\n"
        f"For any fields not listed above, use DCT get-defaults or sensible defaults. "
        f"Then poll job_tool until the link job reaches COMPLETED or FAILED. "
        f"Confirm the final job status.",
        timeout=900,
    )
    if license_blocked(act):
        pytest.skip(
            f"DCT license does not permit {connector_spec.dsource_link_action} operations"
        )
    assert "data_tool" in act.tools_used, (
        f"Claude did not use data_tool. Tools: {sorted(act.tools_used)}\n"
        f"{act.final_text[:300]}"
    )
    assert connector_spec.dsource_link_action in act.actions_for("data_tool"), (
        f"Claude did not call {connector_spec.dsource_link_action}; "
        f"actions: {act.actions_for('data_tool')}"
    )

    # Independent verify (dsource_name NOT in verify prompt)
    verify = drive(
        "Search for all dSources and show each one's name, type, and status."
    )
    assert dsource_name in verify.final_text, (
        f"dSource {dsource_name!r} not found after link.\n"
        f"{verify.final_text[:400]}"
    )

    # Cleanup
    drive(
        f"Delete the dSource named '{dsource_name}'. "
        f"Confirm the deletion and wait for completion.",
        timeout=300,
    )
