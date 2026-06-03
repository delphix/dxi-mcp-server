"""
Layer 5 — AI discoverability for the continuous_data_admin (CDA, admin persona) toolset.

Mirrors tests/llm_local/test_discoverability.py but targets the admin persona via the
`llm_driver_cda` fixture (DCT_TOOLSET=continuous_data_admin). Given ONLY a plain-English
admin task (no tool/action names leaked), does Claude discover and call the RIGHT CDA tool?

Read-only. Driven by the Claude Code CLI; skips cleanly when the `claude` CLI or DCT creds
are unavailable. Each expected tool is asserted to be a real key in the CDA config so the
case list can't drift away from the toolset definition.
"""

import pytest

from tests._support import config_cases

pytestmark = [pytest.mark.real_dct, pytest.mark.llm_driven]

# (plain-English admin task, CDA tool Claude should discover). Tasks avoid naming
# the tool/action. Domains chosen from config_cases.tools_for("continuous_data_admin").
DISCOVERY_CASES = [
    ("List the Delphix engines registered on this system.", "engine_tool"),
    ("What database templates are configured?", "database_template_tool"),
    ("Show the replication profiles.", "replication_tool"),
    ("List the virtualization policies.", "virtualization_policy_tool"),
    ("What tags exist on this system?", "tag_tool"),
    ("Show the toolkits installed.", "toolkit_tool"),
    ("List the groups.", "group_tool"),
]

# Guard: every expected tool must actually exist in the CDA toolset config.
_CDA_TOOLS = set(config_cases.tools_for("continuous_data_admin"))
_BAD = sorted({tool for _task, tool in DISCOVERY_CASES} - _CDA_TOOLS)
assert not _BAD, f"discoverability cases reference tools not in CDA toolset: {_BAD}"


@pytest.mark.parametrize(
    "task,expected_tool", DISCOVERY_CASES, ids=[t for _, t in DISCOVERY_CASES]
)
def test_ai_discovers_right_cda_tool(llm_driver_cda, task, expected_tool):
    result = llm_driver_cda(task)
    assert expected_tool in result.tools_used, (
        f"Claude did not discover {expected_tool} from: {task!r}\n"
        f"Tools it used instead: {sorted(result.tools_used)}\n"
        f"Final answer: {result.final_text[:300]}"
    )
