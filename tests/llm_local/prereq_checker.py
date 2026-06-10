"""
P0 — CDA Prerequisite Chain Checker.

Runs a series of read-only Claude tool calls to verify that the DCT instance
has the full prerequisite chain for running CDA scenarios:

    DCT accessible
      → Engine registered
        → Connector installed on engine   (toolkit for this connector type)
          → Hosts added as environments   (source + target)
            → Repository / source config exists  (discovered after env add)
              → dSource linked             (for this connector type)
                → VDB provisioned          (from that dSource)

Results are cached per pytest SESSION so the ~6 Claude calls happen once,
not once per scenario. Each check uses a real tool call through Claude so
it exercises the actual tool surface.

Usage (fixture):
    def test_something(require_prereqs):
        # auto-skips with a specific message if chain is broken
        ...

    def test_needs_only_engine(require_prereqs_up_to):
        require_prereqs_up_to("engine")   # skips if engine missing, passes if present

Skip message format:
    PREREQ MISSING [<level>]: <what is missing> — <what to run to fix it>
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pytest

# ── levels in dependency order ────────────────────────────────────────────────
LEVELS = ["engine", "connector", "hosts", "source_config", "dsource", "vdb"]

# ── per-level skip messages ───────────────────────────────────────────────────
_SKIP_MESSAGES = {
    "engine": (
        "No Delphix engine registered in DCT. "
        "Run test_cda_setup.py::test_setup_01_engine first."
    ),
    "connector": (
        "Required connector/toolkit not installed on the engine. "
        "Run test_cda_setup.py::test_setup_02_connector first."
    ),
    "hosts": (
        "Source/target host environments not added to the engine. "
        "Run test_cda_setup.py::test_setup_03_hosts first."
    ),
    "source_config": (
        "No repository/source config found for this connector type. "
        "Ensure the environment was added correctly and the plugin discovered repositories. "
        "Run test_cda_setup.py::test_setup_04_source_config first."
    ),
    "dsource": (
        "No dSource of the required type is linked. "
        "Run test_cda_setup.py::test_setup_05_dsource first."
    ),
    "vdb": (
        "No VDB provisioned from the dSource. "
        "Run test_cda_setup.py::test_setup_06_vdb first."
    ),
}

# ── which tools service each CDA scenario group ───────────────────────────────
# Maps tool_name → minimum prereq level needed. If a tool name isn't listed,
# assume it needs no infra prereqs (safe default for reporting/tag/iam tools).
TOOL_PREREQ_LEVEL = {
    "engine_tool": "engine",
    "toolkit_tool": "connector",
    "environment_source_tool": "hosts",
    "staging_source_tool": "hosts",
    "staging_cdb_tool": "hosts",
    "data_connection_tool": "source_config",
    "cdb_dsource_tool": "dsource",
    "dsource_tool": "dsource",
    "snapshot_bookmark_tool": "dsource",
    "timeflow_tool": "dsource",
    "instance_tool": "dsource",
    "data_tool": "vdb",          # VDB lifecycle needs the full chain
    "group_tool": "vdb",
}


@dataclass
class PrereqState:
    """Live snapshot of the DCT prerequisite chain, populated by the checker."""

    engine_id: Optional[str] = None
    engine_name: Optional[str] = None
    connector_ok: bool = False
    connector_name: Optional[str] = None
    hosts: list = field(default_factory=list)      # list of hostname strings
    source_config_ok: bool = False
    dsource_id: Optional[str] = None
    dsource_name: Optional[str] = None
    dsource_type: Optional[str] = None
    vdb_id: Optional[str] = None
    vdb_name: Optional[str] = None

    def first_missing(self) -> Optional[str]:
        """Returns the first unmet prerequisite level name, or None if all met."""
        if not self.engine_id:
            return "engine"
        if not self.connector_ok:
            return "connector"
        if not self.hosts:
            return "hosts"
        if not self.source_config_ok:
            return "source_config"
        if not self.dsource_id:
            return "dsource"
        if not self.vdb_id:
            return "vdb"
        return None

    def is_met_up_to(self, level: str) -> bool:
        """True if every prereq up to and including `level` is satisfied."""
        for lv in LEVELS:
            if not self._level_ok(lv):
                return False
            if lv == level:
                return True
        return True

    def _level_ok(self, level: str) -> bool:
        return {
            "engine": bool(self.engine_id),
            "connector": self.connector_ok,
            "hosts": bool(self.hosts),
            "source_config": self.source_config_ok,
            "dsource": bool(self.dsource_id),
            "vdb": bool(self.vdb_id),
        }[level]

    def skip_message(self, level: str) -> str:
        return f"PREREQ MISSING [{level}]: {_SKIP_MESSAGES[level]}"

    def summary(self) -> str:
        lines = ["DCT Prerequisite Chain:"]
        for lv in LEVELS:
            ok = self._level_ok(lv)
            symbol = "✓" if ok else "✗"
            detail = {
                "engine": self.engine_name or "-",
                "connector": self.connector_name or "-",
                "hosts": ", ".join(self.hosts) or "-",
                "source_config": "present" if self.source_config_ok else "-",
                "dsource": self.dsource_name or "-",
                "vdb": self.vdb_name or "-",
            }[lv]
            lines.append(f"  {symbol} {lv:14} {detail}")
        return "\n".join(lines)


def _extract_ids(text: str, markers: list[str]) -> list[str]:
    """Simple heuristic: look for quoted/backtick-wrapped strings near the markers."""
    import re
    found = []
    for m in markers:
        if m.lower() in text.lower():
            # grab anything in backticks or quotes near the marker
            hits = re.findall(r"[`'\"]([^`'\"]{3,80})[`'\"]", text)
            found.extend(hits)
    return list(dict.fromkeys(found))  # dedupe, preserve order


def check_prerequisites(drive_fn, connector_type: str, target_host: str) -> PrereqState:
    """
    Run the 6-step read-only check against the live DCT via Claude.
    Each step is a single tool call. Returns a fully-populated PrereqState.

    drive_fn: the llm_driver_for("continuous_data_admin") callable
    connector_type: "appdata" | "oracle" | "mssql" | "ase"
    target_host: the host where dSources/VDBs live (short name OK)
    """
    from tests.llm_local.conftest import license_blocked

    state = PrereqState()
    target_short = target_host.split(".")[0]

    # ── 1. Engine ─────────────────────────────────────────────────────────────
    r = drive_fn("List all registered Delphix engines, showing each engine's name, "
                 "hostname, and status.", timeout=120)
    if not license_blocked(r) and r.tools_used:
        # parse the first engine from Claude's answer
        import re
        # look for any name= or hostname= patterns, or any quoted identifier
        names = re.findall(r"(?:name|engine)[:\s]+[`'\"]?([a-zA-Z0-9_.\-]+)[`'\"]?", r.final_text, re.I)
        ids = re.findall(r"id[:\s=]+[`'\"]?([a-zA-Z0-9_.\-]+)[`'\"]?", r.final_text, re.I)
        if "engine" in r.tools_used or r.final_text.strip():
            # if Claude found something, mark engine as present even if parsing is fuzzy
            if any(word in r.final_text.lower() for word in ["engine", "hostname", "registered"]):
                state.engine_id = ids[0] if ids else "found"
                state.engine_name = names[0] if names else "found"
        if not state.engine_id:
            return state  # no engine → stop early

    # ── 2. Connector ──────────────────────────────────────────────────────────
    connector_keywords = {
        "appdata": ["appdata", "plugin", "toolkit"],
        "oracle": ["oracle"],
        "mssql": ["mssql", "sql server"],
        "ase": ["ase", "sybase"],
    }.get(connector_type, [connector_type])

    r2 = drive_fn(
        "List all toolkits and connectors installed on the registered engine. "
        "Show each toolkit's name, version, and which engine it is installed on.",
        timeout=120,
    )
    if not license_blocked(r2):
        ans_lower = r2.final_text.lower()
        for kw in connector_keywords:
            if kw in ans_lower:
                state.connector_ok = True
                state.connector_name = kw
                break
    if not state.connector_ok:
        return state

    # ── 3. Hosts ──────────────────────────────────────────────────────────────
    r3 = drive_fn(
        "List all environments registered in Delphix, showing each environment's "
        "name, hostname, and connection status.",
        timeout=120,
    )
    if not license_blocked(r3):
        import re
        # look for hostnames in the answer (fqdn or short names)
        found = re.findall(r"r\d+[\w.\-]+\.dlpxdc\.co|\b[\w\-]+\.dlpxdc\.co", r3.final_text)
        state.hosts = list(dict.fromkeys(found))
        if not state.hosts and "environment" in r3.final_text.lower():
            # Claude found environments but we couldn't parse hostnames — mark as present
            state.hosts = ["found"]
    if not state.hosts:
        return state

    # ── 4. Source config / repository ─────────────────────────────────────────
    r4 = drive_fn(
        f"Search for repositories and source configs available on the environment "
        f"whose hostname contains '{target_short}'. "
        f"Show each repository's name, type, and which environment it belongs to.",
        timeout=120,
    )
    if not license_blocked(r4):
        ans = r4.final_text.lower()
        # any mention of repository/config found = source_config_ok
        if any(w in ans for w in ["repository", "repo", "source config", "installation", "found", "available"]):
            state.source_config_ok = True
    if not state.source_config_ok:
        return state

    # ── 5. dSource ────────────────────────────────────────────────────────────
    r5 = drive_fn(
        "Search for all dSources and show each one's name, type, and current status.",
        timeout=120,
    )
    if not license_blocked(r5):
        import re
        ans = r5.final_text
        if any(w in ans.lower() for w in ["dsource", "source", "linked"]):
            # try to extract name
            names = re.findall(r"name[:\s]+[`'\"]?([a-zA-Z0-9_.\-]+)[`'\"]?", ans, re.I)
            ids = re.findall(r"\bid[:\s=]+[`'\"]?([a-zA-Z0-9_.\-]+)[`'\"]?", ans, re.I)
            if names or ids:
                state.dsource_id = ids[0] if ids else "found"
                state.dsource_name = names[0] if names else "found"
    if not state.dsource_id:
        return state

    # ── 6. VDB ────────────────────────────────────────────────────────────────
    r6 = drive_fn(
        "Search for all virtual databases (VDBs) and show each one's name and status.",
        timeout=120,
    )
    if not license_blocked(r6):
        import re
        ans = r6.final_text
        if any(w in ans.lower() for w in ["vdb", "virtual database", "running", "stopped"]):
            names = re.findall(r"name[:\s]+[`'\"]?([a-zA-Z0-9_.\-]+)[`'\"]?", ans, re.I)
            ids = re.findall(r"\bid[:\s=]+[`'\"]?([a-zA-Z0-9_.\-]+)[`'\"]?", ans, re.I)
            if names or ids:
                state.vdb_id = ids[0] if ids else "found"
                state.vdb_name = names[0] if names else "found"

    return state


# ── pytest fixtures ───────────────────────────────────────────────────────────

_STATE_CACHE: dict[str, PrereqState] = {}


@pytest.fixture(scope="session")
def cda_prereq_state(llm_driver_for_session):
    """
    Session-scoped: runs the 6-step prereq check ONCE and caches the result.
    Returns the PrereqState (use require_full_prereqs or cda_prereqs to gate tests).
    """
    global _STATE_CACHE
    connector = os.environ.get("CONNECTOR_TYPE", "appdata")
    target = os.environ.get("MYSQL_TARGET_HOST", os.environ.get("DCT_TARGET_HOST", ""))

    cache_key = f"{connector}:{target}"
    if cache_key in _STATE_CACHE:
        return _STATE_CACHE[cache_key]

    if not os.environ.get("DCT_BASE_URL") or not os.environ.get("DCT_API_KEY"):
        pytest.skip("DCT_BASE_URL and DCT_API_KEY required for prereq check")

    drive = llm_driver_for_session("continuous_data_admin")
    state = check_prerequisites(drive, connector, target)
    _STATE_CACHE[cache_key] = state
    print(f"\n{state.summary()}")
    return state


@pytest.fixture
def require_full_prereqs(cda_prereq_state):
    """Skip the test if ANY prerequisite in the chain is missing."""
    missing = cda_prereq_state.first_missing()
    if missing:
        pytest.skip(cda_prereq_state.skip_message(missing))
    return cda_prereq_state


@pytest.fixture
def cda_prereqs(cda_prereq_state):
    """Just returns the state — test decides what to do with it."""
    return cda_prereq_state


def require_prereq_level(state: PrereqState, level: str):
    """
    Call from inside a test to assert a specific level is met.
    pytest.skip if not. Use when a test only needs part of the chain.
    """
    if not state.is_met_up_to(level):
        missing = state.first_missing()
        pytest.skip(state.skip_message(missing))
