"""
Layer 5 — AI discoverability, one case per self_service tool domain.

Given ONLY a plain-English task (no tool/action names leaked), does Claude discover
and call the RIGHT tool? This is the cheap, high-signal usability check: if Claude
can't find the right tool from natural language, the tool names/descriptions are unclear.

Read-only. Driven by the Claude Code CLI (conftest `llm_driver`); skips cleanly when
the `claude` CLI or DCT creds are unavailable.
"""

import pytest

pytestmark = [pytest.mark.real_dct, pytest.mark.llm_driven]

# (plain-English task, tool Claude should discover). Tasks avoid naming the tool/action.
DISCOVERY_CASES = [
    ("How many virtual databases currently exist on this system? Find out and state the count.", "vdb_tool"),
    ("List the VDB groups configured on this system.", "vdb_group_tool"),
    ("What dSources (ingested data sources) exist here?", "dsource_tool"),
    ("Show me the available snapshots and how many there are.", "snapshot_tool"),
    ("What bookmarks have been created on this system?", "bookmark_tool"),
    ("What were the most recent jobs or operations, and did they succeed?", "job_tool"),
    ("Show the timeflows available on this system.", "timeflow_tool"),
]


@pytest.mark.parametrize(
    "task,expected_tool", DISCOVERY_CASES, ids=[t for _, t in DISCOVERY_CASES]
)
def test_ai_discovers_right_tool(llm_driver, task, expected_tool):
    result = llm_driver(task)
    assert expected_tool in result.tools_used, (
        f"Claude did not discover {expected_tool} from: {task!r}\n"
        f"Tools it used instead: {sorted(result.tools_used)}\n"
        f"Final answer: {result.final_text[:300]}"
    )
