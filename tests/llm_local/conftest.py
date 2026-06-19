"""
Layer 5 fixtures (full suite) — LLM-driven E2E against a REAL DCT via the Claude Code CLI.

Hands Claude a plain-English task and asserts on what tools it chose and whether the
operation took effect. Driver:

    claude -p "<task>" --mcp-config <dct.json> --strict-mcp-config \\
        --allowedTools "mcp__delphix-dct__*" --permission-mode bypassPermissions \\
        --append-system-prompt-file .claude/test/llm-driver-preprompt.md \\
        --output-format stream-json --verbose

Advisory, local-only. SKIPs cleanly when the `claude` CLI or DCT creds are absent.
Tests are @pytest.mark.real_dct (real creds flow through) + @pytest.mark.llm_driven
(so `dct-mcp-test --layer llm` selects them).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest

MCP_SERVER_NAME = "delphix-dct"
TOOL_PREFIX = f"mcp__{MCP_SERVER_NAME}__"

# tests/llm_local/conftest.py -> parents[2] == repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PREPROMPT = _REPO_ROOT / ".claude" / "test" / "llm-driver-preprompt.md"


@dataclass
class ToolCall:
    name: str  # bare tool name, e.g. "vdb_tool"
    raw_name: str  # namespaced, e.g. "mcp__delphix-dct__vdb_tool"
    input: dict[str, Any]


@dataclass
class DriverResult:
    returncode: int
    tool_calls: list[ToolCall]
    final_text: str
    events: list[dict[str, Any]]
    raw: str

    @property
    def tools_used(self) -> set[str]:
        return {c.name for c in self.tool_calls}

    def calls_to(self, tool: str) -> list[ToolCall]:
        return [c for c in self.tool_calls if c.name == tool]

    def actions_for(self, tool: str) -> list[str]:
        return [c.input.get("action") for c in self.calls_to(tool) if c.input.get("action")]


def _require_claude_cli() -> str:
    exe = shutil.which("claude")
    if not exe:
        pytest.skip("Claude Code CLI ('claude') not on PATH — required for Layer 5")
    return exe


def _parse_stream_json(stdout: str) -> tuple[list[dict], list[ToolCall], str]:
    events: list[dict] = []
    tool_calls: list[ToolCall] = []
    final_text = ""
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(evt, dict):
            continue
        events.append(evt)
        msg = evt.get("message")
        content = msg.get("content") if isinstance(msg, dict) else None
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    raw = block.get("name", "")
                    bare = raw[len(TOOL_PREFIX):] if raw.startswith(TOOL_PREFIX) else raw
                    tool_calls.append(ToolCall(name=bare, raw_name=raw, input=block.get("input") or {}))
                elif block.get("type") == "text" and block.get("text"):
                    final_text = block["text"]
        if evt.get("type") == "result" and isinstance(evt.get("result"), str):
            final_text = evt["result"]
    return events, tool_calls, final_text


def _write_mcp_config(toolset: str) -> Path:
    """
    Write a temp MCP config for `toolset` derived from `.mcp.json`.

    Reads the `delphix-dct` server definition from `.mcp.json` (the single
    source of truth), overrides DCT_TOOLSET + injects runtime credentials from
    the environment, and writes a per-session temp file for `claude -p
    --mcp-config`. Skips if credentials are absent. Caller must unlink the path.
    """
    base_url = os.environ.get("DCT_BASE_URL")
    api_key = os.environ.get("DCT_API_KEY")
    if not base_url or not api_key:
        pytest.skip(
            "DCT_BASE_URL and DCT_API_KEY are required for Layer 5 — run via "
            "`dct-mcp-test --layer llm --base-url ... --api-key ...`"
        )

    # Read server definition from .mcp.json
    mcp_json_path = _REPO_ROOT / ".mcp.json"
    base_config = json.loads(mcp_json_path.read_text())
    server = base_config["mcpServers"][MCP_SERVER_NAME]

    server_env = {
        k: os.path.expandvars(v) if isinstance(v, str) else v
        for k, v in server.get("env", {}).items()
    }
    server_env.update({
        "DCT_API_KEY": api_key,
        "DCT_BASE_URL": base_url,
        "DCT_TOOLSET": toolset,
        "DCT_VERIFY_SSL": "false",
        "DCT_LOG_LEVEL": "ERROR",
        "DCT_TIMEOUT": "30",
        "DCT_MAX_RETRIES": "3",
    })
    # Propagate TMPDIR for generation isolation (safe-run venv → $TEMP, not src/)
    if os.environ.get("TMPDIR"):
        server_env["TMPDIR"] = os.environ["TMPDIR"]

    config = {"mcpServers": {MCP_SERVER_NAME: {
        "command": server["command"],
        "args": server.get("args", []),
        "env": server_env,
    }}}
    fd, path = tempfile.mkstemp(prefix=f"dct-mcp-{toolset}-", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(config, f)
    return Path(path)


def _make_driver(
    config_path: Path,
    extra_preprompts: list[Path] | None = None,
) -> Callable[..., DriverResult]:
    """
    Build a `run(task)` closure that drives the Claude Code CLI against `config_path`.

    extra_preprompts: additional --append-system-prompt-file paths (e.g. connector
    context) appended AFTER the job-completion pre-prompt. Claude sees them all.
    """
    exe = _require_claude_cli()
    preprompt = str(_PREPROMPT) if _PREPROMPT.exists() else None
    # Default to haiku — Sonnet 4.6 intermittently returns HTTP 500 for DCT ops.
    # Override with LLM_MODEL env var (e.g. LLM_MODEL=claude-sonnet-4-6).
    model = os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001")

    def run(task: str, *, timeout: int = 180) -> DriverResult:
        cmd = [
            exe, "-p", task,
            "--model", model,
            "--mcp-config", str(config_path),
            "--strict-mcp-config",
            "--allowedTools", f"{TOOL_PREFIX}*",
            "--permission-mode", "bypassPermissions",
            "--output-format", "stream-json",
            "--verbose",
        ]
        if preprompt:
            cmd.extend(["--append-system-prompt-file", preprompt])
        for ep in (extra_preprompts or []):
            if ep.exists():
                cmd.extend(["--append-system-prompt-file", str(ep)])
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            pytest.fail(f"Claude Code CLI timed out after {timeout}s for task: {task!r}")
        if proc.returncode != 0 and not proc.stdout.strip():
            pytest.skip(
                f"Claude Code CLI exited {proc.returncode} with no output — likely not "
                f"authenticated (run `claude` once to log in). stderr:\n{proc.stderr[:500]}"
            )
        events, tool_calls, final_text = _parse_stream_json(proc.stdout)
        return DriverResult(proc.returncode, tool_calls, final_text, events, proc.stdout)

    return run


@pytest.fixture(scope="session")
def dct_mcp_config() -> Iterator[Path]:
    """Temp MCP config pointing dct-mcp-server at the REAL DCT (self_service)."""
    path = _write_mcp_config("self_service")
    try:
        yield path
    finally:
        os.unlink(path)


@pytest.fixture(scope="session")
def dct_mcp_config_cda() -> Iterator[Path]:
    """Temp MCP config pointing dct-mcp-server at the REAL DCT (continuous_data_admin)."""
    path = _write_mcp_config("continuous_data_admin")
    try:
        yield path
    finally:
        os.unlink(path)


@pytest.fixture
def llm_driver(dct_mcp_config: Path) -> Callable[..., DriverResult]:
    """Run a natural-language task through the Claude Code CLI (self_service)."""
    return _make_driver(dct_mcp_config)


@pytest.fixture
def llm_driver_cda(dct_mcp_config_cda: Path) -> Callable[..., DriverResult]:
    """Run a natural-language task through the Claude Code CLI (continuous_data_admin)."""
    return _make_driver(dct_mcp_config_cda)


# --- S0: per-persona driver factory + Claude-side license tolerance ----------

LICENSE_MARKER = "License does not permit"


def license_blocked(result: DriverResult) -> bool:
    """
    True if the run hit a DCT license restriction (a tool returned
    "License does not permit operations on <X>"). Scenario tests should skip
    (resource not licensed on this DCT), not fail.
    """
    blob = (result.raw or "") + " " + (result.final_text or "")
    return LICENSE_MARKER in blob


@pytest.fixture(scope="session")
def llm_driver_for_session():
    """
    Session-scoped version of llm_driver_for — used by session-scoped fixtures
    like cda_prereq_state. Creates configs once, cleans up at session end.
    """
    configs: dict[str, Path] = {}

    def make(toolset: str) -> Callable[..., DriverResult]:
        if toolset not in configs:
            configs[toolset] = _write_mcp_config(toolset)
        return _make_driver(configs[toolset])

    yield make

    for path in configs.values():
        try:
            os.unlink(path)
        except OSError:
            pass


@pytest.fixture
def llm_driver_for():
    """
    Factory fixture: `llm_driver_for()(toolset) -> run(task)` for ANY toolset.

        drive = llm_driver_for()
        result = drive("platform_admin")("List the registered engines")

    Writes a temp MCP config per toolset (skips the test if creds/claude absent),
    caches per toolset, and cleans up all temp configs on teardown.
    """
    configs: dict[str, Path] = {}

    def make(toolset: str) -> Callable[..., DriverResult]:
        if toolset not in configs:
            configs[toolset] = _write_mcp_config(toolset)
        return _make_driver(configs[toolset])

    yield make

    for path in configs.values():
        try:
            os.unlink(path)
        except OSError:
            pass


# Re-export P0 prereq fixtures so they're auto-discovered by pytest.
# The implementations live in prereq_checker.py; we just import here.
from tests.llm_local.prereq_checker import (  # noqa: E402,F401
    cda_prereq_state,
    require_full_prereqs,
    cda_prereqs,
)
from tests.llm_local.connector_fixtures import (  # noqa: E402,F401
    connector_spec,
    engine_spec,
    write_connector_preprompt,
)


@pytest.fixture
def llm_driver_for_connector(connector_spec, llm_driver_for):
    """
    Returns a `run(task)` callable that drives Claude with BOTH:
      1. The job-completion pre-prompt (wait for async jobs)
      2. A connector context pre-prompt (field docs + resolved values from schema/.secrets.yaml)

    Use this for prompts taken directly from .claude/test/testing/*.md so Claude
    can handle "Link an AppData dSource using those defaults" without needing
    fields pre-embedded in the prompt.

        driver = llm_driver_for_connector
        result = driver("Link an AppData dSource using those defaults with a test name")
    """
    import tempfile, os as _os

    # Write connector pre-prompt to a temp file (session-scoped content)
    preprompt_path = write_connector_preprompt(connector_spec)
    mcp_config_path = _write_mcp_config("continuous_data_admin")

    driver = _make_driver(mcp_config_path, extra_preprompts=[preprompt_path])

    yield driver

    # Cleanup temp files
    for p in [preprompt_path, mcp_config_path]:
        try:
            p.unlink()
        except OSError:
            pass
# llm_driver_for_session is defined above in this file and used by cda_prereq_state
