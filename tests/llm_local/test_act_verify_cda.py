"""
Layer 5 — admin (continuous_data_admin) act -> verify scenarios, Claude-driven.

Same pattern as test_act_verify.py but for the admin persona via llm_driver_for(CDA):
hand Claude a plain-English mutation, wait (job-completion pre-prompt), then verify the
real effect with an INDEPENDENT read whose prompt does NOT contain the identifier being
checked (so a passing assertion means the effect truly persisted, not an echo).

GATED: skipped unless LLM_ALLOW_MUTATION=1 — run only against a disposable / cloned DCT.
"""

import json
import os

import pytest

from tests.llm_local.conftest import license_blocked

pytestmark = [pytest.mark.real_dct, pytest.mark.llm_driven]

_MUTATION = os.environ.get("LLM_ALLOW_MUTATION") == "1"
_ENGINE_JSON = os.environ.get("E2E_ENGINE_JSON")


@pytest.mark.skipif(not _MUTATION, reason="LLM_ALLOW_MUTATION=1 not set — tags a real engine")
def test_ai_tags_engine_then_independently_verifies(llm_driver_for):
    """Admin act->verify on a licensed resource (engine tags) — needs no external creds."""
    drive = llm_driver_for("continuous_data_admin")
    run_tag = os.environ.get("E2E_RUN_TAG", "e2e-local")
    key = f"e2e_{run_tag.replace('-', '_')}"

    # --- ACT ---
    act = drive(
        f"Add the tag {key}=scenario to the first Delphix engine registered on this "
        f"system. Wait until it is applied, then confirm.",
        timeout=300,
    )
    if license_blocked(act):
        pytest.skip("DCT license does not permit engine tag operations")
    if "no engine" in act.final_text.lower() or "no engines" in act.final_text.lower():
        pytest.skip("Claude reports no engine registered to tag (not a failure)")
    assert "engine_tool" in act.tools_used, (
        f"Claude did not use engine_tool. Tools: {sorted(act.tools_used)}\n{act.final_text[:300]}"
    )
    assert "add_tags" in act.actions_for("engine_tool"), (
        f"Claude did not call add_tags; actions: {act.actions_for('engine_tool')}"
    )

    # --- INDEPENDENT VERIFY (key NOT in the prompt) ---
    verify = drive("List every tag currently on the first engine, showing each tag's key and value.")
    assert "engine_tool" in verify.tools_used, (
        f"verification did not read the engine; tools: {sorted(verify.tools_used)}"
    )
    assert key in verify.final_text, (
        f"independent verify did not find tag {key!r} on the engine. Answer: {verify.final_text[:400]}"
    )

    # --- CLEANUP ---
    drive(f"Remove the tag {key} from the first engine.")


@pytest.mark.skipif(
    not (_MUTATION and _ENGINE_JSON),
    reason="set LLM_ALLOW_MUTATION=1 AND E2E_ENGINE_JSON (engine register payload) to run",
)
def test_ai_registers_engine_then_verifies_then_unregisters(llm_driver_for):
    """
    The admin add-engine workflow, Claude-driven. Requires E2E_ENGINE_JSON — the engine
    register payload, e.g. {"hostname":"...","type":"...","username":"...","password":"..."}.
    register -> wait for job -> verify the hostname appears in the engine list -> unregister.
    """
    drive = llm_driver_for("continuous_data_admin")
    payload = json.loads(_ENGINE_JSON)
    hostname = payload.get("hostname") or payload.get("host")
    assert hostname, "E2E_ENGINE_JSON must include a 'hostname'"

    # --- ACT (register; pre-prompt waits for the job) ---
    act = drive(
        f"Register a new Delphix engine using exactly these details: {json.dumps(payload)}. "
        f"Wait until the registration job has fully completed, then confirm.",
        timeout=600,
    )
    if license_blocked(act):
        pytest.skip("DCT license does not permit engine registration")
    assert "engine_tool" in act.tools_used, f"Claude did not use engine_tool: {sorted(act.tools_used)}"
    assert "register" in act.actions_for("engine_tool"), (
        f"Claude did not call register; actions: {act.actions_for('engine_tool')}"
    )

    # --- INDEPENDENT VERIFY (hostname NOT in the prompt) ---
    verify = drive("List all registered Delphix engines, showing each engine's hostname.")
    assert hostname in verify.final_text, (
        f"engine {hostname!r} not found after register. Answer: {verify.final_text[:400]}"
    )

    # --- CLEANUP (unregister) ---
    drive(f"Unregister the Delphix engine whose hostname is {hostname}. Confirm the operation.")
