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
    if "no vdb" in result.final_text.lower() or "no virtual database" in result.final_text.lower():
        pytest.skip("Claude reports no VDB available to bookmark (not a failure)")

    assert "bookmark_tool" in result.tools_used, (
        f"Claude did not use bookmark_tool to create. Tools: {sorted(result.tools_used)}\n"
        f"Answer: {result.final_text[:300]}"
    )

    # --- VERIFY via an INDEPENDENT read ---
    verify = llm_driver(
        f"Search the bookmarks for one named '{name}' and tell me whether it exists."
    )
    actions = verify.actions_for("bookmark_tool")
    assert any(a in ("search", "get", "list") for a in actions), (
        f"verification did not perform an independent bookmark read; actions: {actions}"
    )
    assert name in verify.final_text, (
        f"independent verification did not confirm bookmark {name!r} exists. "
        f"Claude's answer: {verify.final_text[:400]}"
    )
