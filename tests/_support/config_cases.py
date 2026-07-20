"""
config_cases — the parametrization engine behind "full coverage, efficiently".

Parses the SAME config files the server reads (`config/toolsets/*.txt`,
`config/mappings/manual_confirmation.txt`) into pytest-friendly case lists, so a
single parametrized test fans out across every action / confirmation rule / toolset
without hand-written duplicates.

It parses the `.txt` files INDEPENDENTLY of `dct_mcp_server.config.loader` on purpose:
that way these cases are a ground-truth oracle the loader unit tests can assert against,
rather than being derived from the code under test.

Public API:
    toolset_names()                  -> list[str]
    tools_for(toolset)               -> dict[str, list[ApiCase]]   (tool -> actions)
    action_cases(toolset=None)       -> list[ActionCase]
    confirmation_rules()             -> list[ConfirmRule]
    action_id(case) / rule_id(rule)  -> stable pytest ids
"""

from __future__ import annotations

import re
from collections import namedtuple
from functools import lru_cache
from pathlib import Path

import dct_mcp_server

_CONFIG_DIR = Path(dct_mcp_server.__file__).resolve().parent / "config"
TOOLSETS_DIR = _CONFIG_DIR / "toolsets"
CONFIRMATION_FILE = _CONFIG_DIR / "mappings" / "manual_confirmation.txt"

# A single action mapping within a tool: METHOD|path|action under a `# TOOL N: name` header.
ActionCase = namedtuple("ActionCase", "toolset tool method path action")
# A confirmation rule: METHOD|path_pattern|level|message_template.
ConfirmRule = namedtuple("ConfirmRule", "method path level message")

_TOOL_HEADER = re.compile(r"^#\s*TOOL\s+\d+:\s*([A-Za-z0-9_]+)\s*-")
_ACTION_LINE = re.compile(r"^[A-Z*]+\|")


def toolset_names() -> list[str]:
    """All toolset names (the *.txt filenames without extension), sorted."""
    return sorted(p.stem for p in TOOLSETS_DIR.glob("*.txt"))


@lru_cache(maxsize=None)
def tools_for(toolset: str) -> dict:
    """
    Parse one toolset into {tool_name: [(method, path, action), ...]}, resolving
    `@inherit:parent` (parent parsed first; this file's tools extend/append).
    Returned dict values are lists of (method, path, action) tuples.
    """
    path = TOOLSETS_DIR / f"{toolset}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Unknown toolset: {toolset} ({path})")

    tools: dict[str, list] = {}
    current = None
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("@inherit:"):
            parent = line.split(":", 1)[1].strip()
            # Seed with the parent's tools (deep-ish copy of the lists).
            for t, apis in tools_for(parent).items():
                tools.setdefault(t, []).extend(apis)
            continue
        header = _TOOL_HEADER.match(line)
        if header:
            current = header.group(1)
            tools.setdefault(current, [])
            continue
        if _ACTION_LINE.match(line):
            parts = line.split("|")
            if len(parts) < 3 or current is None:
                continue
            method, api_path, action = (
                parts[0].strip(),
                parts[1].strip(),
                parts[2].strip(),
            )
            entry = (method, api_path, action)
            if entry not in tools[current]:
                tools[current].append(entry)
    return tools


def action_cases(toolset: str | None = None) -> list:
    """Flat list of ActionCase across one toolset, or all toolsets if None."""
    names = [toolset] if toolset else toolset_names()
    cases: list = []
    for ts in names:
        for tool, apis in tools_for(ts).items():
            for method, api_path, action in apis:
                cases.append(ActionCase(ts, tool, method, api_path, action))
    return cases


@lru_cache(maxsize=1)
def confirmation_rules() -> tuple:
    """All confirmation rules from manual_confirmation.txt as ConfirmRule tuples."""
    rules: list = []
    for raw in CONFIRMATION_FILE.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|", 3)
        if len(parts) < 3:
            continue
        method = parts[0].strip()
        api_path = parts[1].strip()
        level = parts[2].strip()
        message = parts[3].strip() if len(parts) > 3 else ""
        rules.append(ConfirmRule(method, api_path, level, message))
    return tuple(rules)


def action_id(case: ActionCase) -> str:
    """Stable, readable pytest id for an ActionCase."""
    return f"{case.toolset}-{case.tool}-{case.action}"


def rule_id(rule: ConfirmRule) -> str:
    """Stable pytest id for a ConfirmRule."""
    return f"{rule.method}-{rule.path}-{rule.level}"
