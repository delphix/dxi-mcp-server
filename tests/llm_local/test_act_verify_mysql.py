"""
Layer 5 — MySQL dSource (AppData) act → verify scenarios, Claude-driven.

Exercises the real MySQL/AppData write path on the disposable DCT:
  1. Add the MySQL host as an environment (if not already present)
  2. Link a MySQL dSource via AppData → wait for job → verify → cleanup

Credentials supplied via env vars (never hardcoded):
  MYSQL_HOST          — the MySQL source hostname (e.g. r95-mys-s11.dlpxdc.co)
  MYSQL_ENV_USER      — OS user to add the environment (e.g. mysql)
  MYSQL_ENV_PASSWORD  — OS password for that user (e.g. connect_123)
  MYSQL_LINK_USER     — OS user for link/provision (e.g. delphix_os)
  MYSQL_LINK_PASSWORD — password for link/provision (e.g. Delphix@123)

GATED: skipped unless LLM_ALLOW_MUTATION=1 AND MYSQL_HOST is set.
Run via the safe-run venv against a DISPOSABLE DCT only.
"""

import os

import pytest

from tests.llm_local.conftest import license_blocked

pytestmark = [pytest.mark.real_dct, pytest.mark.llm_driven]

_MUTATION = os.environ.get("LLM_ALLOW_MUTATION") == "1"
_MYSQL_HOST = os.environ.get("MYSQL_HOST", "")
_ENV_USER = os.environ.get("MYSQL_ENV_USER", "mysql")
_ENV_PASS = os.environ.get("MYSQL_ENV_PASSWORD", "")
_LINK_USER = os.environ.get("MYSQL_LINK_USER", "delphix_os")
_LINK_PASS = os.environ.get("MYSQL_LINK_PASSWORD", "")

_SKIP_REASON = (
    "Set LLM_ALLOW_MUTATION=1 AND MYSQL_HOST / MYSQL_ENV_PASSWORD / MYSQL_LINK_PASSWORD "
    "to run the MySQL dSource scenarios."
)


@pytest.mark.skipif(
    not (_MUTATION and _MYSQL_HOST and _ENV_PASS and _LINK_PASS),
    reason=_SKIP_REASON,
)
def test_ai_adds_mysql_environment(llm_driver_for):
    """
    Add the MySQL host as a Delphix environment.
    act → wait for job → verify the environment hostname appears in the list.
    """
    drive = llm_driver_for("continuous_data_admin")
    run_tag = os.environ.get("E2E_RUN_TAG", "e2e-local")
    short_host = _MYSQL_HOST.split(".")[0]

    # --- ACT ---
    act = drive(
        f"Add the host '{_MYSQL_HOST}' as a new Unix/Linux environment in Delphix. "
        f"Use username='{_ENV_USER}' and password='{_ENV_PASS}' for the environment credentials. "
        f"Call the appropriate environment tool action directly with all required fields. "
        f"Then use job_tool to poll until the job reaches a terminal state. "
        f"Then confirm the final job status.",
        timeout=600,
    )
    if license_blocked(act):
        pytest.skip("DCT license does not permit environment operations")
    assert "environment_source_tool" in act.tools_used or "environment_tool" in act.tools_used, (
        f"Claude did not use an environment tool. Tools: {sorted(act.tools_used)}\n{act.final_text[:300]}"
    )

    # --- INDEPENDENT VERIFY (short hostname NOT in prompt) ---
    verify = drive(
        "List all environments registered in Delphix, showing each environment's hostname."
    )
    assert short_host in verify.final_text, (
        f"Environment {_MYSQL_HOST!r} (short: {short_host!r}) not found after adding.\n"
        f"Claude's answer: {verify.final_text[:400]}"
    )


@pytest.mark.skipif(
    not (_MUTATION and _MYSQL_HOST and _ENV_PASS and _LINK_PASS),
    reason=_SKIP_REASON,
)
def test_ai_links_mysql_dsource_and_verifies(llm_driver_for):
    """
    Link a MySQL dSource via AppData → wait for job → verify it appears → cleanup.
    Assumes the host is already registered as an environment (run test_ai_adds_mysql_environment
    first, or ensure it's present).
    """
    drive = llm_driver_for("continuous_data_admin")
    run_tag = os.environ.get("E2E_RUN_TAG", "e2e-local")
    dsource_name = f"{run_tag}-mysql-ds"
    short_host = _MYSQL_HOST.split(".")[0]

    # --- GET DEFAULTS (discover the right AppData parameters for this DCT) ---
    defaults = drive(
        f"Get the default parameters for linking an AppData dSource from the environment "
        f"on host '{_MYSQL_HOST}'. Show all required and optional parameters.",
        timeout=180,
    )
    if license_blocked(defaults):
        pytest.skip("DCT license does not permit dSource link operations")

    # --- ACT: LINK ---
    act = drive(
        f"Link a new AppData (MySQL) dSource named '{dsource_name}' from the environment "
        f"on host '{_MYSQL_HOST}'. "
        f"Use the environment user '{_LINK_USER}' with password '{_LINK_PASS}'. "
        f"Use default parameters where possible. "
        f"Call data_tool with action=dsource_link_appdata with all required fields. "
        f"Then use job_tool to poll until the link job reaches COMPLETED or FAILED. "
        f"Then confirm the final job status.",
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
        f"Claude did not poll job_tool; may not have waited for job completion.\n{act.final_text[:300]}"
    )

    # --- INDEPENDENT VERIFY (dsource_name NOT in prompt) ---
    verify = drive(
        f"Search for all dSources linked from host '{short_host}', "
        f"showing each dSource's name and status."
    )
    assert dsource_name in verify.final_text, (
        f"dSource {dsource_name!r} not found after link.\nClaude's answer: {verify.final_text[:400]}"
    )

    # --- CLEANUP ---
    drive(
        f"Delete the dSource named '{dsource_name}'. Confirm the operation and wait for completion.",
        timeout=300,
    )
