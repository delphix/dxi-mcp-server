"""
Layer 5 fixtures — LLM-driven E2E against a REAL DCT, driven by the Claude Code CLI.

Unlike Layers 1-3 (no LLM) and Layer 4 (scripted real-DCT), Layer 5 hands Claude a
plain-English task and asserts on *what tools it chose* and *whether the operation
actually took effect*. The driver is the headless Claude Code CLI:

    claude -p "<task>" --mcp-config <dct.json> --strict-mcp-config \\
        --allowedTools "mcp__delphix-dct__*" --permission-mode bypassPermissions \\
        --append-system-prompt-file .claude/test/llm-driver-preprompt.md \\
        --output-format stream-json --verbose

These tests are advisory and local-only. They SKIP cleanly when the `claude` CLI or
DCT credentials are unavailable, so they never break the rest of the suite.

Every test here is marked @pytest.mark.real_dct (needs a live DCT, so the root conftest
leaves real creds intact) and @pytest.mark.llm_driven (so `dct-mcp-test --layer llm`
can select them).
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

# Shared job-completion pre-prompt (documented in .claude/test/testing.md).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PREPROMPT = _REPO_ROOT / ".claude" / "test" / "llm-driver-preprompt.md"


@dataclass
class ToolCall:
    """One MCP tool invocation Claude made during a run."""

    name: str  # bare tool name, e.g. "vdb_tool"
    raw_name: str  # namespaced, e.g. "mcp__delphix-dct__vdb_tool"
    input: dict[str, Any]


@dataclass
class DriverResult:
    """Parsed outcome of one `claude -p` run."""

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
    """
    Parse Claude Code's newline-delimited stream-json into (events, tool_calls,
    final_text). Tool calls come from `tool_use` blocks in assistant messages;
    the final text comes from the terminal `result` event (or the last text block).
    """
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
                    tool_calls.append(
                        ToolCall(name=bare, raw_name=raw, input=block.get("input") or {})
                    )
                elif block.get("type") == "text" and block.get("text"):
                    final_text = block["text"]

        if evt.get("type") == "result" and isinstance(evt.get("result"), str):
            final_text = evt["result"]

    return events, tool_calls, final_text


@pytest.fixture(scope="session")
def dct_mcp_config() -> Iterator[Path]:
    """
    Write a temp MCP config that points the dct-mcp-server at the REAL DCT, the
    way `claude --mcp-config` expects. Skips the whole layer if creds are absent.
    """
    base_url = os.environ.get("DCT_BASE_URL")
    api_key = os.environ.get("DCT_API_KEY")
    if not base_url or not api_key:
        pytest.skip(
            "DCT_BASE_URL and DCT_API_KEY are required for Layer 5 — run via "
            "`dct-mcp-test --layer llm --base-url ... --api-key ...`"
        )

    config = {
        "mcpServers": {
            MCP_SERVER_NAME: {
                "command": sys.executable,
                "args": ["-m", "dct_mcp_server.main"],
                "env": {
                    "DCT_API_KEY": api_key,
                    "DCT_BASE_URL": base_url,
                    "DCT_TOOLSET": "self_service",
                    "DCT_VERIFY_SSL": "false",
                    "DCT_LOG_LEVEL": "ERROR",
                    "DCT_TIMEOUT": "30",
                    "DCT_MAX_RETRIES": "3",
                },
            }
        }
    }

    fd, path = tempfile.mkstemp(prefix="dct-mcp-", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(config, f)
    try:
        yield Path(path)
    finally:
        os.unlink(path)


@pytest.fixture
def llm_driver(dct_mcp_config: Path) -> Callable[..., DriverResult]:
    """
    Returns a callable that runs a natural-language task through the Claude Code
    CLI against the real-DCT MCP server, and parses the tool-call trace:

        result = llm_driver("How many VDBs exist? Use the tools to find out.")
        assert "vdb_tool" in result.tools_used
    """
    exe = _require_claude_cli()
    preprompt = str(_PREPROMPT) if _PREPROMPT.exists() else None

    def run(task: str, *, timeout: int = 180) -> DriverResult:
        cmd = [
            exe,
            "-p",
            task,
            "--mcp-config",
            str(dct_mcp_config),
            "--strict-mcp-config",
            "--allowedTools",
            f"{TOOL_PREFIX}*",
            "--permission-mode",
            "bypassPermissions",
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        if preprompt:
            cmd.extend(["--append-system-prompt-file", preprompt])

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            pytest.fail(f"Claude Code CLI timed out after {timeout}s for task: {task!r}")

        if proc.returncode != 0 and not proc.stdout.strip():
            # Most common cause: not logged in. Skip rather than report a false failure.
            pytest.skip(
                f"Claude Code CLI exited {proc.returncode} with no output — likely not "
                f"authenticated (run `claude` once to log in). stderr:\n{proc.stderr[:500]}"
            )

        events, tool_calls, final_text = _parse_stream_json(proc.stdout)
        return DriverResult(
            returncode=proc.returncode,
            tool_calls=tool_calls,
            final_text=final_text,
            events=events,
            raw=proc.stdout,
        )

    return run
