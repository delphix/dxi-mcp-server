"""
Layer 5 — AI-usability smoke (discoverability).

Read-only. Proves that, given ONLY a plain-English task and the tool schemas,
Claude discovers and calls the right self_service tool. This is the cheap signal:
if Claude can't even find vdb_tool/search from a VDB question, the tool names or
descriptions are unclear.

Driven by the Claude Code CLI (see conftest.llm_driver). Skips cleanly when the
`claude` CLI or DCT credentials are unavailable.

    dct-mcp-test --layer llm --base-url https://localhost --api-key <key>
"""

import pytest

pytestmark = [pytest.mark.real_dct, pytest.mark.llm_driven]


def test_ai_discovers_and_uses_vdb_search(llm_driver):
    """A plain-English VDB question should lead Claude to vdb_tool / search."""
    result = llm_driver(
        "How many virtual databases (VDBs) currently exist on this system? "
        "Use the available tools to find out, then state the count."
    )

    assert "vdb_tool" in result.tools_used, (
        "Claude did not discover vdb_tool from a plain-English VDB question. "
        f"Tools it used instead: {sorted(result.tools_used)}\n"
        f"Final answer: {result.final_text[:300]}"
    )

    actions = result.actions_for("vdb_tool")
    assert any(a in ("search", "list") for a in actions), (
        f"Expected a search/list action on vdb_tool; saw actions: {actions}"
    )


def test_ai_uses_job_tool_for_a_job_question(llm_driver):
    """A question about job/operation status should lead Claude to job_tool."""
    result = llm_driver(
        "What were the most recent jobs or operations on this system, and did they "
        "succeed? Use the available tools to check."
    )

    assert "job_tool" in result.tools_used, (
        "Claude did not discover job_tool from a plain-English jobs question. "
        f"Tools it used instead: {sorted(result.tools_used)}\n"
        f"Final answer: {result.final_text[:300]}"
    )
