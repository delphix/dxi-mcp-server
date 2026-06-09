"""
Layer 5 — MySQL dSource (AppData) act → verify scenarios, Claude-driven.

Exercises the real MySQL/AppData write path on the disposable DCT:
  1. Add the MySQL host as an environment (if not already present)
  2. Link a MySQL dSource via AppData → wait for job → verify → cleanup

Topology:
  MYSQL_SOURCE_HOST   — source MySQL host (e.g. r95-mys-s11.dlpxdc.co) — add as environment
  MYSQL_TARGET_HOST   — target MySQL host (e.g. r95-mys-t11.dlpxdc.co) — add as environment + link here
  MYSQL_ENV_USER      — OS user to add environments (e.g. mysql)
  MYSQL_ENV_PASSWORD  — OS password for environment user (e.g. connect_123)
  MYSQL_LINK_USER     — OS user for link/provision (e.g. delphix_os)
  MYSQL_LINK_PASSWORD — password for link/provision (e.g. Delphix@123)

GATED: skipped unless LLM_ALLOW_MUTATION=1 AND MYSQL_TARGET_HOST is set.
Run via the safe-run venv against a DISPOSABLE DCT only.
"""

import os

import pytest

from tests.llm_local.conftest import license_blocked

pytestmark = [pytest.mark.real_dct, pytest.mark.llm_driven]

_MUTATION = os.environ.get("LLM_ALLOW_MUTATION") == "1"
_SOURCE_HOST = os.environ.get("MYSQL_SOURCE_HOST", "")   # add as env (no link here)
_TARGET_HOST = os.environ.get("MYSQL_TARGET_HOST", "")   # add as env + link from here
_ENV_USER = os.environ.get("MYSQL_ENV_USER", "mysql")
_ENV_PASS = os.environ.get("MYSQL_ENV_PASSWORD", "")
_LINK_USER = os.environ.get("MYSQL_LINK_USER", "delphix_os")
_LINK_PASS = os.environ.get("MYSQL_LINK_PASSWORD", "")

_SKIP_REASON = (
    "Set LLM_ALLOW_MUTATION=1 AND MYSQL_TARGET_HOST / MYSQL_ENV_PASSWORD / MYSQL_LINK_PASSWORD "
    "to run the MySQL dSource scenarios."
)


@pytest.mark.skipif(
    not (_MUTATION and (_SOURCE_HOST or _TARGET_HOST) and _ENV_PASS),
    reason=_SKIP_REASON,
)
def test_ai_adds_both_mysql_environments(llm_driver_for):
    """
    Add BOTH MySQL hosts as Delphix environments (source + target).
    Each: act → wait for job → independent verify hostname appears.
    """
    drive = llm_driver_for("continuous_data_admin")
    hosts = [h for h in [_SOURCE_HOST, _TARGET_HOST] if h]

    for host in hosts:
        short = host.split(".")[0]

        # --- ACT ---
        act = drive(
            f"Add the host '{host}' as a new Unix/Linux environment in Delphix. "
            f"Use username='{_ENV_USER}' and password='{_ENV_PASS}' for the SSH credentials. "
            f"Call the appropriate environment tool action with all required fields. "
            f"Then use job_tool to poll until the job reaches a terminal state. "
            f"Confirm the final job status.",
            timeout=600,
        )
        if license_blocked(act):
            pytest.skip("DCT license does not permit environment operations")
        assert "environment_source_tool" in act.tools_used or "environment_tool" in act.tools_used, (
            f"Claude did not use an environment tool for {host}. "
            f"Tools: {sorted(act.tools_used)}\n{act.final_text[:300]}"
        )

        # --- INDEPENDENT VERIFY (short hostname NOT in prompt) ---
        verify = drive(
            "List all environments registered in Delphix, showing each environment's hostname."
        )
        assert short in verify.final_text, (
            f"Environment {host!r} (short: {short!r}) not found after adding.\n"
            f"Claude's answer: {verify.final_text[:400]}"
        )


@pytest.mark.skipif(
    not (_MUTATION and _TARGET_HOST and _ENV_PASS and _LINK_PASS),
    reason=_SKIP_REASON,
)
def test_ai_links_mysql_dsource_on_target_and_verifies(llm_driver_for):
    """
    Link a MySQL AppData dSource on the TARGET host (r95-mys-t11) →
    wait for job → independent verify → cleanup.

    The SOURCE host (r95-mys-s11) is already registered as an environment but the
    link operation runs against the TARGET host (r95-mys-t11).
    """
    drive = llm_driver_for("continuous_data_admin")
    run_tag = os.environ.get("E2E_RUN_TAG", "e2e-local")
    dsource_name = f"{run_tag}-mysql-ds"
    short_target = _TARGET_HOST.split(".")[0]

    # --- ACT: LINK on target host ---
    act = drive(
        f"Link a new AppData dSource named '{dsource_name}' using the environment "
        f"on host '{_TARGET_HOST}' (the target/staging host). "
        f"Environment user: '{_LINK_USER}', password: '{_LINK_PASS}'. "
        f"Use data_tool action=dsource_link_appdata. "
        f"Search for the right environment and repository on '{_TARGET_HOST}' automatically. "
        f"For required fields you cannot determine, use sensible defaults. "
        f"Then use job_tool to poll until the link job reaches COMPLETED or FAILED. "
        f"Confirm the final job status.",
        timeout=900,
    )
    if license_blocked(act):
        pytest.skip("DCT license does not permit dSource link operations")
    assert "data_tool" in act.tools_used, (
        f"Claude did not use data_tool to link. Tools: {sorted(act.tools_used)}\n{act.final_text[:300]}"
    )
    assert "dsource_link_appdata" in act.actions_for("data_tool"), (
        f"Claude did not call dsource_link_appdata; actions: {act.actions_for('data_tool')}"
    )
    assert "job_tool" in act.tools_used, (
        f"Claude did not poll job_tool; may not have waited for link job.\n{act.final_text[:300]}"
    )

    # --- INDEPENDENT VERIFY (dsource_name and target host NOT in verify prompt) ---
    verify = drive(
        "Search for all dSources and show each one's name, type, and current status."
    )
    assert dsource_name in verify.final_text, (
        f"dSource {dsource_name!r} not found after link.\nClaude's answer: {verify.final_text[:500]}"
    )

    # --- CLEANUP ---
    drive(
        f"Delete the dSource named '{dsource_name}'. Confirm the deletion and wait for completion.",
        timeout=300,
    )
