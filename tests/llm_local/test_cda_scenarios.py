"""
P3 — Full CDA scenario suite: all 431 continuous_data_admin.md prompts, gated
by the prerequisite chain.

Every prompt is classified by its tool's minimum prereq level (TOOL_PREREQ_LEVEL).
The prereq state is checked ONCE per session (session-cached via cda_prereq_state)
and each test skips with a specific message if its required level isn't met.

Smart gating levels (current DCT state gates 245 runnable / 186 gated):
  no prereq   → iam_tool, reporting_tool, tag_tool, diagnostic_tool, vault_tool, job_tool
  engine      → engine_tool
  connector   → toolkit_tool
  hosts       → environment_source_tool, staging_*, group_tool
  source_cfg  → data_connection_tool
  dsource     → snapshot_bookmark_tool, instance_tool, timeflow_tool, cdb_dsource_tool
  vdb         → data_tool (VDB lifecycle), group_tool (VDB groups)

Run all runnable prompts:
    set -a; source .env.local; set +a
    .venv-live/bin/python -m pytest tests/llm_local/test_cda_scenarios.py -m llm_driven -v

Run with mutations included (disposable DCT only):
    SCENARIO_MUTATIONS=1 LLM_ALLOW_MUTATION=1 \\
    .venv-live/bin/python -m pytest tests/llm_local/test_cda_scenarios.py -m llm_driven -v
"""

import os

import pytest

from tests._support import config_cases, scenarios as S
from tests.llm_local.conftest import license_blocked
from tests.llm_local.prereq_checker import (
    LEVELS,
    TOOL_PREREQ_LEVEL,
    require_prereq_level,
)

# Connector-specific mutation prompts from the .md file.
# Claude reads the raw prompt, uses the connector pre-prompt (schema + resolved fields)
# to figure out what action/fields to use, and discovers env/repo IDs from DCT.
_CONNECTOR_MUTATIONS = [
    s for s in S.load_scenarios("continuous_data_admin")
    if s.tier == "mutation"
    and any(w in s.prompt.lower() for w in [
        "appdata", "oracle", "ase", "mssql", "link", "dsource", "provision",
        "snapshot", "refresh", "vdb"
    ])
]

pytestmark = [pytest.mark.real_dct, pytest.mark.llm_driven]

_ALLOW_MUTATIONS = os.environ.get("SCENARIO_MUTATIONS") == "1"

# Pre-compute all CDA scenarios at import time (fast — just parses the .md file)
_ALL = S.load_scenarios("continuous_data_admin")

# Known issues from previous live runs (xfail so they stay visible but don't block)
_KNOWN_ISSUES = {
    "continuous_data_admin-161":
        "chained prompt ('that vCDB') has no antecedent when run in isolation",
    "continuous_data_admin-407":
        "DISCOVERABILITY GAP: vault_tool not surfaced for 'Hashicorp vaults'",
    "continuous_data_admin-408":
        "DISCOVERABILITY GAP: vault_tool not surfaced for 'Hashicorp vaults'",
}

# CDA persona tool set (for Tier-1: Claude used a CDA tool)
_CDA_TOOLS = set(config_cases.tools_for("continuous_data_admin"))


def _scenarios_to_run():
    """All CDA scenarios, optionally filtered to read-tier only."""
    if _ALLOW_MUTATIONS:
        return list(_ALL)
    return [s for s in _ALL if s.tier == "read"]


_CASES = _scenarios_to_run()


@pytest.mark.parametrize(
    "scenario",
    _CONNECTOR_MUTATIONS,
    ids=[s.id for s in _CONNECTOR_MUTATIONS],
)
def test_cda_connector_mutation(cda_prereq_state, llm_driver_for_connector, scenario):
    """
    Connector mutation prompts from continuous_data_admin.md, driven by Claude.

    Prompts are taken VERBATIM from the .md file (e.g. "Link an AppData dSource
    using those defaults"). Claude uses the connector context pre-prompt (schema
    field docs + resolved values from .secrets.yaml) to figure out what action and
    fields to use, and discovers environment/repository IDs from DCT via tools.

    Gated: SCENARIO_MUTATIONS=1 + LLM_ALLOW_MUTATION=1 + connector secrets set.
    """
    if not (os.environ.get("SCENARIO_MUTATIONS") == "1"
            and os.environ.get("LLM_ALLOW_MUTATION") == "1"):
        pytest.skip(
            "Set SCENARIO_MUTATIONS=1 and LLM_ALLOW_MUTATION=1 to run connector mutations."
        )

    if scenario.id in _KNOWN_ISSUES:
        pytest.xfail(_KNOWN_ISSUES[scenario.id])

    needed_level = TOOL_PREREQ_LEVEL.get(scenario.tool)
    if needed_level and not cda_prereq_state.is_met_up_to(needed_level):
        missing = cda_prereq_state.first_missing()
        pytest.skip(cda_prereq_state.skip_message(missing))

    # Drive with the connector-aware driver (schema + credentials in pre-prompt)
    result = llm_driver_for_connector(scenario.prompt, timeout=600)

    if license_blocked(result):
        pytest.skip(f"{scenario.id}: DCT license does not permit this operation")

    used_cda = result.tools_used & _CDA_TOOLS
    assert used_cda, (
        f"{scenario.id} [{scenario.tier}] Claude used NO CDA tool. "
        f"tools_used={sorted(result.tools_used)}\n"
        f"  prompt: {scenario.prompt}\n"
        f"  answer: {result.final_text[:200]}"
    )


@pytest.mark.parametrize("scenario", _CASES, ids=[s.id for s in _CASES])
def test_cda_scenario(cda_prereq_state, llm_driver_for, scenario):
    """
    Run one CDA scenario prompt through Claude → Tier-1 verify.
    Skips with a specific prereq message if the required chain level is unmet.
    """
    # ── xfail known issues ────────────────────────────────────────────────────
    if scenario.id in _KNOWN_ISSUES:
        pytest.xfail(_KNOWN_ISSUES[scenario.id])

    # ── smart prereq gate (per tool, not a session-wide all-or-nothing) ──────
    needed_level = TOOL_PREREQ_LEVEL.get(scenario.tool)  # None = no infra needed
    if needed_level is not None:
        if not cda_prereq_state.is_met_up_to(needed_level):
            missing = cda_prereq_state.first_missing()
            pytest.skip(
                f"PREREQ MISSING [{missing}] for {scenario.tool!r}: "
                f"{cda_prereq_state.skip_message(missing)}"
            )

    # ── license tolerance ─────────────────────────────────────────────────────
    drive = llm_driver_for("continuous_data_admin")
    result = drive(scenario.prompt, timeout=300)

    if license_blocked(result):
        pytest.skip(
            f"{scenario.id}: DCT license does not permit this operation "
            f"(tool: {scenario.tool})"
        )

    # ── Tier-1: Claude used a CDA tool (not a refusal/hallucination) ─────────
    used_cda = result.tools_used & _CDA_TOOLS
    assert used_cda, (
        f"{scenario.id} [{scenario.tier}] expected a CDA tool; "
        f"Claude used: {sorted(result.tools_used)}\n"
        f"  prompt: {scenario.prompt}\n"
        f"  answer: {result.final_text[:200]}"
    )
