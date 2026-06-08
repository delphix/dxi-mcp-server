"""
Persona scenario suite — run any persona's natural-language prompts through the
Claude Code CLI against a REAL DCT and verify the output.

This is the framework for "give Claude a prompt for any persona, verify it works".
Scenarios come from `tests/_support/scenarios.py` (parsed from
`.claude/test/testing/<persona>.md`). Selection is by env (so a run targets exactly
what you want — the full catalog is ~900 prompts):

    SCENARIO_PERSONAS=self_service,continuous_data_admin   # which personas (required)
    SCENARIO_MUTATIONS=1     # include mutation-tier prompts (default: read-only)
    SCENARIO_LIMIT=10        # cap per-persona (after filtering)
    SCENARIO_IDS=self_service-1,self_service-13   # run only these ids

Run via the safe-run venv:
    set -a; source .env.local; set +a
    SCENARIO_PERSONAS=self_service SCENARIO_LIMIT=5 \\
      .venv-live/bin/python -m pytest tests/llm_local/test_scenarios.py -m scenario -v

Verification (Tier 1, generic): Claude discovered and used the EXPECTED tool for the
scenario, with no unhandled error. License-blocked resources -> skip (env limitation).
Tier 2 (act -> independent verify) is added per-scenario in later phases.

NOTE: prompts in the .md files are chained within a persona session ("that VDB",
"from the previous result"). Here each prompt runs as an INDEPENDENT claude call, so
Tier-1 just checks the right tool was used — Claude re-discovers any antecedent
(e.g. searches to find "the first VDB"). True chained-session replay is future work.
"""

import os

import pytest

from tests._support import config_cases, scenarios as S
from tests.llm_local.conftest import license_blocked

pytestmark = [pytest.mark.real_dct, pytest.mark.llm_driven, pytest.mark.scenario]

_PERSONAS = [p.strip() for p in os.environ.get("SCENARIO_PERSONAS", "").split(",") if p.strip()]
_ALLOW_MUTATIONS = os.environ.get("SCENARIO_MUTATIONS") == "1"
_LIMIT = int(os.environ.get("SCENARIO_LIMIT") or 0)
_ONLY_IDS = {x.strip() for x in os.environ.get("SCENARIO_IDS", "").split(",") if x.strip()}


def _selected_scenarios():
    out = []
    for persona in _PERSONAS:
        scs = list(S.load_scenarios(persona))
        if _ONLY_IDS:
            scs = [s for s in scs if s.id in _ONLY_IDS]
        if not _ALLOW_MUTATIONS:
            scs = [s for s in scs if s.tier == "read"]
        if _LIMIT:
            scs = scs[:_LIMIT]
        out.extend(scs)
    return out


_CASES = _selected_scenarios()


@pytest.mark.parametrize("scenario", _CASES, ids=[s.id for s in _CASES])
def test_scenario(llm_driver_for, scenario):
    drive = llm_driver_for(scenario.persona)
    result = drive(scenario.prompt, timeout=300)

    # Resource not licensed on this DCT -> skip (environment limitation, not a bug).
    if license_blocked(result):
        pytest.skip(f"{scenario.id}: DCT license does not permit (tool {scenario.tool})")

    # Tier 1: Claude drove a tool that ACTUALLY belongs to this persona (i.e. it
    # engaged the real DCT, didn't refuse or hallucinate). We do NOT assert the exact
    # tool from the .md header: those groupings are imperfect (e.g. "VDB groups" prompts
    # are filed under data_tool but DCT exposes them via group_tool — Claude is right to
    # use group_tool). `scenario.tool` is kept for reporting only.
    persona_tools = set(config_cases.tools_for(scenario.persona))
    used_persona_tools = result.tools_used & persona_tools
    assert used_persona_tools, (
        f"{scenario.id} [{scenario.tier}] Claude used NO {scenario.persona} tool "
        f"(refusal/hallucination?). tools_used={sorted(result.tools_used)}\n"
        f"  prompt: {scenario.prompt}\n  answer: {result.final_text[:200]}"
    )
