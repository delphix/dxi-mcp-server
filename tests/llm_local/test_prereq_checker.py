"""
P0 validation — tests for the prerequisite checker itself.

Verifies the checker correctly reads the DCT state and produces accurate
PrereqState results. Run once to validate P0 before building P2–P4.
"""

import pytest

from tests.llm_local.prereq_checker import (
    PrereqState, LEVELS, TOOL_PREREQ_LEVEL, require_prereq_level
)

pytestmark = [pytest.mark.real_dct, pytest.mark.llm_driven]


# ── Unit tests (offline, no DCT) ─────────────────────────────────────────────

def test_prereq_state_first_missing_empty():
    s = PrereqState()
    assert s.first_missing() == "engine"


def test_prereq_state_first_missing_chain():
    s = PrereqState(engine_id="1", engine_name="e", connector_ok=True,
                    hosts=["h1"], source_config_ok=True)
    assert s.first_missing() == "dsource"


def test_prereq_state_all_met():
    s = PrereqState(engine_id="1", engine_name="e", connector_ok=True,
                    hosts=["h"], source_config_ok=True,
                    dsource_id="ds1", dsource_name="ds",
                    vdb_id="v1", vdb_name="vdb")
    assert s.first_missing() is None


def test_is_met_up_to():
    s = PrereqState(engine_id="1", engine_name="e", connector_ok=True, hosts=["h"])
    assert s.is_met_up_to("engine")
    assert s.is_met_up_to("connector")
    assert not s.is_met_up_to("source_config")


def test_skip_message_format():
    s = PrereqState()
    msg = s.skip_message("dsource")
    assert "PREREQ MISSING [dsource]" in msg
    assert "test_setup_05_dsource" in msg


def test_tool_prereq_level_coverage():
    assert TOOL_PREREQ_LEVEL["data_tool"] == "vdb"
    assert TOOL_PREREQ_LEVEL["engine_tool"] == "engine"
    assert TOOL_PREREQ_LEVEL["dsource_tool"] == "dsource"


def test_levels_order():
    assert LEVELS == ["engine", "connector", "hosts", "source_config", "dsource", "vdb"]


# ── Live test (real DCT, cached) ─────────────────────────────────────────────

def test_prereq_checker_reads_live_dct_state(cda_prereq_state):
    """
    Verify the checker accurately reflects the CURRENT DCT state.
    Expected (from DCT inspection 2026-06-10):
      engine ✓ (qa-dev-test11)  connector ✓ (AppData)
      hosts ✓ (s11 + t11)       source_config = TBD
      dsource ✗                 vdb ✗
    Prints the full chain summary for manual review.
    """
    state = cda_prereq_state
    print(f"\n{state.summary()}")

    # Hard assertions on what we KNOW is present
    assert state.engine_id, "Engine should be present (qa-dev-test11 was registered)"
    assert state.connector_ok, "AppData connector/toolkit should be installed"
    assert state.hosts, "Both MySQL environments should be registered"

    # Soft assertions on what we expect to be ABSENT
    assert not state.dsource_id, (
        f"No dSource should exist yet (none linked) — found: {state.dsource_name}"
    )
    assert not state.vdb_id, (
        f"No VDB should exist yet — found: {state.vdb_name}"
    )

    # The first missing step should be source_config or dsource
    missing = state.first_missing()
    assert missing in ("source_config", "dsource"), (
        f"Expected first_missing to be source_config or dsource, got: {missing!r}\n"
        f"{state.summary()}"
    )
