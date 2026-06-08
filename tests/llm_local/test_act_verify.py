"""
Layer 5 — act -> wait -> verify (the full pattern), driven by Claude.

Hand Claude a plain-English MUTATION task; the job-completion pre-prompt makes it wait
for any async job and then verify the real effect through an independent read. We assert
both that Claude drove the right tools AND that the effect actually persisted.

Bookmarks are used because self_service can fully manage them (create + delete), so the
flow is self-contained and the created object is named with E2E_RUN_TAG for the cleanup
pass to purge.

GATED: skipped unless LLM_ALLOW_MUTATION=1 — run only against a disposable / cloned DCT.
Also skips if the DCT has no VDB to bookmark.
"""

import os

import pytest

from tests.llm_local.conftest import license_blocked

pytestmark = [pytest.mark.real_dct, pytest.mark.llm_driven]

_MUTATION = os.environ.get("LLM_ALLOW_MUTATION") == "1"
_SKIP = "LLM_ALLOW_MUTATION=1 not set — this test has Claude create+verify a real bookmark."


@pytest.mark.skipif(not _MUTATION, reason=_SKIP)
def test_ai_creates_bookmark_then_independently_verifies(llm_driver):
    run_tag = os.environ.get("E2E_RUN_TAG", "e2e-llm-local")
    name = f"{run_tag}-bookmark"

    # --- ACT (+ wait, enforced by the pre-prompt) ---
    result = llm_driver(
        f"Create a bookmark named '{name}' on the first available VDB. Wait until the "
        f"operation has fully completed before telling me the result.",
        timeout=600,
    )
    if license_blocked(result):
        pytest.skip("DCT license does not permit bookmark operations")
    if "no vdb" in result.final_text.lower() or "no virtual database" in result.final_text.lower():
        pytest.skip("Claude reports no VDB available to bookmark (not a failure)")

    assert "bookmark_tool" in result.tools_used, (
        f"Claude did not use bookmark_tool to create. Tools: {sorted(result.tools_used)}\n"
        f"Answer: {result.final_text[:300]}"
    )

    # --- VERIFY via an INDEPENDENT read ---
    # The name must NOT appear in the verify prompt, else Claude echoes it regardless of
    # existence. Ask for the full list and assert the run-tagged name shows up.
    verify = llm_driver("List all bookmarks in the system, showing each bookmark's name.")
    if license_blocked(verify):
        pytest.skip("DCT license does not permit bookmark operations")
    assert "bookmark_tool" in verify.tools_used, (
        f"verification did not read bookmarks; tools: {sorted(verify.tools_used)}"
    )
    assert name in verify.final_text, (
        f"independent verification did not find bookmark {name!r} in the list. "
        f"Claude's answer: {verify.final_text[:400]}"
    )


@pytest.mark.skipif(not _MUTATION, reason="LLM_ALLOW_MUTATION=1 not set — tags a real VDB")
def test_ai_tags_vdb_then_independently_verifies_then_cleans_up(llm_driver):
    """
    act -> independent verify -> cleanup on a LICENSED resource (VDB tags), so it runs
    on DCTs that don't license bookmarks. A unique run-tagged key makes it self-cleaning
    and collision-free. Independent verification = a SEPARATE Claude call re-reads the
    tags (not trusting the act call's own claim).
    """
    run_tag = os.environ.get("E2E_RUN_TAG", "e2e-llm-local")
    key, val = f"e2e_{run_tag.replace('-', '_')}", "scenario"

    # --- ACT ---
    act = llm_driver(
        f"Add the tag {key}={val} to the first VDB in the system. Wait until it is applied, "
        f"then confirm.",
        timeout=300,
    )
    if license_blocked(act):
        pytest.skip("DCT license does not permit VDB tag operations")
    if "no vdb" in act.final_text.lower() or "no virtual database" in act.final_text.lower():
        pytest.skip("Claude reports no VDB available to tag (not a failure)")
    assert "vdb_tool" in act.tools_used, (
        f"Claude did not use vdb_tool to tag. Tools: {sorted(act.tools_used)}\n{act.final_text[:300]}"
    )
    assert "add_tags" in act.actions_for("vdb_tool"), (
        f"Claude did not call add_tags; actions: {act.actions_for('vdb_tool')}"
    )

    # --- INDEPENDENT VERIFY (fresh call re-reads the tags) ---
    # Do NOT put the key in the prompt (else Claude echoes it regardless). Ask for ALL
    # tags and assert our run-tagged key shows up — that only happens if it truly exists.
    # Don't constrain WHICH read action Claude uses (search may return tags inline).
    verify = llm_driver("List every tag currently on the first VDB, showing each tag's key and value.")
    assert "vdb_tool" in verify.tools_used, (
        f"verification did not read the VDB via vdb_tool; tools: {sorted(verify.tools_used)}"
    )
    assert key in verify.final_text, (
        f"independent verify did not find tag {key!r} on the VDB. Claude's answer: {verify.final_text[:400]}"
    )

    # --- CLEANUP (remove the tag) ---
    llm_driver(f"Remove the tag {key} from the first VDB.")
