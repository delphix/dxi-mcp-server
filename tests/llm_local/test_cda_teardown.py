"""
P4 — CDA teardown: reverse-order cleanup after the setup + scenario runs.

Deletes objects created by the P2 setup flow, in reverse order:
    06b  VDB                   (if exists)
    05c  dSource               (if exists, tagged or named with run_tag)
    03b  Environments          (source + target, if added by this run)
    01b  Engine unregister     (OPTIONAL — only with TEARDOWN_UNREGISTER_ENGINE=1)

Each step:
  1. Direct API idempotence check — skip if the object isn't there.
  2. Claude drives the delete/unregister with confirmation embedded.
  3. Direct API verification — confirms the object is gone.

GATED: requires LLM_ALLOW_MUTATION=1.
Engine unregister requires TEARDOWN_UNREGISTER_ENGINE=1 (separate gate — the engine
may be shared and you don't always want to unregister it after a test run).

Run:
    set -a; source .env.local; set +a
    export E2E_RUN_TAG="cda-setup-..."   # same tag used during setup
    LLM_ALLOW_MUTATION=1 .venv-live/bin/python -m pytest \\
      tests/llm_local/test_cda_teardown.py -m llm_driven -v -s
"""

import os

import pytest
import requests

from tests.llm_local.conftest import license_blocked
from tests.llm_local.connector_fixtures import ConnectorSpec

pytestmark = [pytest.mark.real_dct, pytest.mark.llm_driven]

_MUTATION = os.environ.get("LLM_ALLOW_MUTATION") == "1"
_UNREGISTER_ENGINE = os.environ.get("TEARDOWN_UNREGISTER_ENGINE") == "1"
_SKIP = "Set LLM_ALLOW_MUTATION=1 to run CDA teardown steps."


# ── Direct API helpers ────────────────────────────────────────────────────────

def _dct(method: str, path: str, body: dict | None = None) -> dict:
    base = os.environ.get("DCT_BASE_URL", "").rstrip("/")
    key = os.environ.get("DCT_API_KEY", "")
    fn = getattr(requests, method.lower())
    r = fn(
        f"{base}/dct/v3/{path}",
        json=body or {},
        headers={"Authorization": f"apk {key}"},
        verify=False,
        timeout=15,
    )
    if r.ok:
        return r.json()
    return {}


def _vdbs() -> list:
    return _dct("post", "vdbs/search", {"limit": 20}).get("items", [])

def _dsources() -> list:
    return _dct("post", "dsources/search", {"limit": 20}).get("items", [])

def _environments() -> list:
    return _dct("post", "environments/search", {"limit": 20}).get("items", [])

def _engines() -> list:
    return _dct("post", "management/engines/search", {"limit": 10}).get("items", [])


# ── Teardown steps (reverse of setup, numbered with 'b'/'c' suffix) ───────────

@pytest.mark.skipif(not _MUTATION, reason=_SKIP)
def test_teardown_06b_vdb(connector_spec: ConnectorSpec, llm_driver_for):
    """Delete all VDBs created by this run. Skip if none exist."""
    run_tag = os.environ.get("E2E_RUN_TAG", "")
    vdbs = _vdbs()
    if not vdbs:
        pytest.skip("No VDBs found on DCT — nothing to tear down.")

    # Filter to run-tagged ones if tag is set; otherwise delete all (test DCT only!)
    targets = [v for v in vdbs if run_tag and run_tag in (v.get("name") or "")]
    if not targets:
        targets = vdbs  # no tag filter — take all (disposable DCT assumed)

    drive = llm_driver_for("continuous_data_admin")
    for vdb in targets:
        vdb_name = vdb.get("name") or vdb.get("id")
        print(f"\n  Deleting VDB: {vdb_name}")
        act = drive(
            f"Delete the VDB named '{vdb_name}'. "
            f"Use data_tool with the delete VDB action. "
            f"This operation requires confirmation — pass confirmed=True. "
            f"Then use job_tool to poll until the job reaches COMPLETED or FAILED. "
            f"Confirm the final status.",
            timeout=600,
        )
        if license_blocked(act):
            pytest.skip("DCT license does not permit VDB deletion")
        assert "data_tool" in act.tools_used, (
            f"Claude did not use data_tool to delete VDB {vdb_name!r}.\n"
            f"{act.final_text[:200]}"
        )

    # Direct API verify: all targeted VDBs gone
    remaining = _vdbs()
    remaining_names = {v.get("name") for v in remaining}
    deleted = [t.get("name") for t in targets if t.get("name") not in remaining_names]
    print(f"\n  VDBs deleted: {deleted}")
    assert not any(t.get("name") in remaining_names for t in targets), (
        f"Some VDBs still present after teardown: "
        f"{[t.get('name') for t in targets if t.get('name') in remaining_names]}"
    )


@pytest.mark.skipif(not _MUTATION, reason=_SKIP)
def test_teardown_05c_dsource(connector_spec: ConnectorSpec, llm_driver_for):
    """Delete all dSources created by this run. Skip if none exist."""
    run_tag = os.environ.get("E2E_RUN_TAG", "")
    dsources = _dsources()
    if not dsources:
        pytest.skip("No dSources found on DCT — nothing to tear down.")

    targets = [d for d in dsources if run_tag and run_tag in (d.get("name") or "")]
    if not targets:
        targets = dsources

    drive = llm_driver_for("continuous_data_admin")
    for ds in targets:
        ds_name = ds.get("name") or ds.get("id")
        print(f"\n  Deleting dSource: {ds_name}")
        act = drive(
            f"Delete the dSource named '{ds_name}'. "
            f"Use data_tool with the delete dSource action. "
            f"This operation requires confirmation — pass confirmed=True. "
            f"Then use job_tool to poll until the job reaches COMPLETED or FAILED. "
            f"Confirm the final status.",
            timeout=600,
        )
        if license_blocked(act):
            pytest.skip("DCT license does not permit dSource deletion")
        assert "data_tool" in act.tools_used, (
            f"Claude did not use data_tool to delete dSource {ds_name!r}.\n"
            f"{act.final_text[:200]}"
        )

    # Direct API verify
    remaining = {d.get("name") for d in _dsources()}
    still_present = [t.get("name") for t in targets if t.get("name") in remaining]
    assert not still_present, (
        f"dSources still present after teardown: {still_present}"
    )


@pytest.mark.skipif(not _MUTATION, reason=_SKIP)
def test_teardown_03b_environments(connector_spec: ConnectorSpec, llm_driver_for):
    """Remove source + target environments added by this run."""
    envs = _environments()
    hosts_to_remove = [connector_spec.source_host, connector_spec.target_host]
    targets = [
        e for e in envs
        if any(h.split(".")[0] in (e.get("name") or e.get("address") or "")
               for h in hosts_to_remove)
    ]
    if not targets:
        pytest.skip(
            f"Environments {hosts_to_remove} not found — already removed or never added."
        )

    drive = llm_driver_for("continuous_data_admin")
    for env in targets:
        env_name = env.get("name") or env.get("address") or env.get("id")
        short = env_name.split(".")[0] if "." in env_name else env_name
        print(f"\n  Removing environment: {env_name}")
        act = drive(
            f"Delete the environment named '{env_name}'. "
            f"Use environment_source_tool with the delete environment action. "
            f"This operation requires confirmation — pass confirmed=True. "
            f"Then use job_tool to poll until the job reaches COMPLETED or FAILED. "
            f"Confirm the final status.",
            timeout=600,
        )
        if license_blocked(act):
            pytest.skip("DCT license does not permit environment deletion")
        assert (
            "environment_source_tool" in act.tools_used
            or "environment_tool" in act.tools_used
        ), (
            f"Claude did not use an environment tool to delete {env_name!r}.\n"
            f"{act.final_text[:200]}"
        )

    # Direct API verify
    remaining_names = {
        e.get("name") or e.get("address") for e in _environments()
    }
    still_present = [
        t.get("name") or t.get("address")
        for t in targets
        if (t.get("name") or t.get("address")) in remaining_names
    ]
    assert not still_present, (
        f"Environments still present after teardown: {still_present}"
    )


@pytest.mark.skipif(
    not (_MUTATION and _UNREGISTER_ENGINE),
    reason=(
        "Set LLM_ALLOW_MUTATION=1 AND TEARDOWN_UNREGISTER_ENGINE=1 to unregister the engine. "
        "Skipped by default — the engine may be shared."
    ),
)
def test_teardown_01b_engine(connector_spec: ConnectorSpec, llm_driver_for):
    """
    Unregister the engine. OPTIONAL — only runs with TEARDOWN_UNREGISTER_ENGINE=1.
    Do NOT set this flag if the engine is shared or needed by other tests.
    """
    engines = _engines()
    if not engines:
        pytest.skip("No engines registered — nothing to unregister.")

    drive = llm_driver_for("continuous_data_admin")
    for engine in engines:
        engine_name = engine.get("name") or engine.get("hostname")
        print(f"\n  Unregistering engine: {engine_name}")
        act = drive(
            f"Unregister the Delphix engine named '{engine_name}'. "
            f"Use engine_tool action=unregister. "
            f"This requires confirmation — pass confirmed=True. "
            f"Then use job_tool to poll until the job reaches COMPLETED or FAILED. "
            f"Confirm the final status.",
            timeout=600,
        )
        if license_blocked(act):
            pytest.skip("DCT license does not permit engine unregistration")
        assert "engine_tool" in act.tools_used, (
            f"Claude did not use engine_tool to unregister {engine_name!r}.\n"
            f"{act.final_text[:200]}"
        )

    # Direct API verify
    remaining = _engines()
    assert not remaining, (
        f"Engines still registered after unregister: "
        f"{[e.get('name') for e in remaining]}"
    )
