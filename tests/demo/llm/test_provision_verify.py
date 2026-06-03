"""
Layer 5 — act -> wait -> verify (the full pattern, the centerpiece of this layer).

Hand Claude a provisioning task in plain English; let it discover and call the tool;
WAIT for the async job to finish (enforced by the job-completion pre-prompt at
.claude/test/llm-driver-preprompt.md); then VERIFY through an INDEPENDENT read that
the VDB actually exists. A tool returning "success" is not proof — provisioning is
asynchronous and may only mean "job submitted".

This test MUTATES a real DCT, so it is SKIPPED unless LLM_ALLOW_MUTATION=1 is set, and
must be run only against a disposable / cloned DCT. The created VDB is named with
E2E_RUN_TAG so tests/e2e/cleanup can purge it.

    LLM_ALLOW_MUTATION=1 dct-mcp-test --layer llm --base-url https://localhost --api-key <key>
"""

import os

import pytest

pytestmark = [pytest.mark.real_dct, pytest.mark.llm_driven]

_MUTATION_ALLOWED = os.environ.get("LLM_ALLOW_MUTATION") == "1"
_SKIP_REASON = (
    "LLM_ALLOW_MUTATION=1 not set — this test provisions a real VDB. "
    "Set it (and point at a disposable/cloned DCT) to exercise act -> verify."
)


@pytest.mark.skipif(not _MUTATION_ALLOWED, reason=_SKIP_REASON)
def test_provision_then_independently_verify_vdb_exists(llm_driver):
    run_tag = os.environ.get("E2E_RUN_TAG", "e2e-llm-local")
    vdb_name = f"{run_tag}-vdb"

    # --- PHASE 1+2: act + wait ---------------------------------------------
    # The pre-prompt requires Claude to poll the job to a terminal state before
    # claiming success, so this single call should not return until the VDB is
    # provisioned (or the job failed).
    result = llm_driver(
        f"Provision a new VDB named '{vdb_name}' from the first available dSource. "
        f"Wait until the provisioning job has fully completed before telling me the "
        f"final result.",
        timeout=900,
    )

    assert "vdb_tool" in result.tools_used, (
        "Claude did not call vdb_tool to provision. "
        f"Tools used: {sorted(result.tools_used)}\nAnswer: {result.final_text[:300]}"
    )
    # The job-completion pre-prompt requires polling — job_tool must have been used.
    assert "job_tool" in result.tools_used, (
        "Claude reported a result without polling job_tool — the job-completion "
        "pre-prompt was not honored (success may be on submission only). "
        f"Tools used: {sorted(result.tools_used)}"
    )

    # --- PHASE 3: verify via an INDEPENDENT read ---------------------------
    # A fresh search, NOT the provision call, must confirm the VDB persisted.
    verify = llm_driver(
        f"Search the VDBs for one named '{vdb_name}'. Tell me whether it exists and "
        f"what its status is."
    )

    verify_actions = verify.actions_for("vdb_tool")
    assert any(a in ("search", "list", "get") for a in verify_actions), (
        f"Verification did not perform an independent read on vdb_tool; "
        f"saw actions: {verify_actions}"
    )
    assert vdb_name in verify.final_text, (
        f"Independent verification did not confirm VDB '{vdb_name}' exists on the "
        f"real DCT. Claude's answer: {verify.final_text[:400]}"
    )
