"""Guard against internal terminology re-entering user-facing text (PPM-1129).

These assert on everything shipped that the model reads or a user can be
shown: confirmation message templates, tool and action names (toolset .txt
files and the pre-built tool modules), and the docstrings of every pre-built
tool. They are deliberately cheap so that a future rule, action or docstring
added with the wrong vocabulary fails at merge time rather than in front of a
customer.
"""

import ast
import re
from pathlib import Path

import pytest

from dct_mcp_server.config.loader import (
    MAPPINGS_DIR,
    load_manual_confirmation_rules,
)

# Terms that must never appear in a message shown to a user. "engine" is
# checked separately, since it is only wrong when unqualified.
_BANNED = [
    "timeflow",
    "appdata",
    "toolkit",
    "plugin",
    "mssql",
    "inventory",
    "cloud engine",
    "delphix masking",
    "virtualization engine",
    "masking engine",
    "rewind",
    "container",
    "delphix engine",
]

_SRC = Path(__file__).resolve().parents[2] / "src/dct_mcp_server"
_PREBUILT_TOOL_FILES = sorted((_SRC / "tools").glob("*_endpoints_tool.py"))


def _rule_messages():
    return [r.get("message", "") for r in load_manual_confirmation_rules()]


@pytest.mark.parametrize("term", _BANNED)
def test_no_confirmation_message_uses_internal_term(term):
    offenders = [m for m in _rule_messages() if re.search(rf"\b{term}\b", m, re.I)]
    assert not offenders, f"{term!r} leaks in: {offenders}"


def test_engine_is_always_qualified_in_confirmation_messages():
    for message in _rule_messages():
        for match in re.finditer(r"\bengine\b", message, re.IGNORECASE):
            preceding = message[: match.start()].rstrip().lower()
            assert preceding.endswith("continuous data") or preceding.endswith(
                "continuous compliance"
            ), f'unqualified "engine" in: {message}'


def test_vdb_group_casing_is_canonical():
    for message in _rule_messages():
        assert "VDB group" not in message, f"should be 'VDB Group': {message}"


def test_no_confirmation_message_contains_a_pipe():
    """The rule parser splits on '|', so a pipe would truncate the message."""
    raw = (MAPPINGS_DIR / "manual_confirmation.txt").read_text()
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert len(line.split("|")) == 4, f"wrong field count: {line}"


def test_tool_docstrings_are_free_of_internal_jargon():
    """discovery/execute docstrings are the only tool descriptions the model sees."""
    source = (
        Path(__file__).resolve().parents[2] / "src/dct_mcp_server/tools/core/dynamic.py"
    ).read_text()

    for marker in ("def discovery(", "    async def execute("):
        start = source.index(marker)
        open_q = source.index('"""', start)
        docstring = source[open_q : source.index('"""', open_q + 3)]
        for jargon in ("FR-00", "EC-6", "DCTAPIClient", "embedding host"):
            assert jargon not in docstring, f"{jargon!r} leaks in {marker.strip()}"


# --------------------------------------------------------------------------- #
# Tool and action names
# --------------------------------------------------------------------------- #

# Identifier fragments that contain a banned word but are legitimate, each for
# a stated reason. Anything not listed here fails.
_NAME_EXCEPTIONS = {
    # DCT's /reporting/vdb-inventory-report is a Continuous Data report listing
    # VDBs -- not the retired Continuous Compliance "inventory" (rule set).
    "vdb_inventory_report",
}
# "mssql" is non-canonical in prose but not a glossary-retired term; action
# names mirror the /dsources/mssql and /sources/mssql API resources alongside
# *_oracle_* and *_ase_*, so it is not checked in identifiers.
_NAME_BANNED = [t for t in _BANNED if t != "mssql"]


def _name_offences(name: str) -> list[str]:
    cleaned = name.lower()
    for allowed in _NAME_EXCEPTIONS:
        cleaned = cleaned.replace(allowed, "_")
    tokens = "_" + "_".join(re.split(r"[_\-\s]+", cleaned)) + "_"
    return [
        term
        for term in _NAME_BANNED
        if f"_{term.replace(' ', '_')}_" in tokens
        or f"_{term.replace(' ', '')}_" in tokens
    ]


def _toolset_names():
    names = set()
    for path in sorted((_SRC / "config/toolsets").glob("*.txt")):
        for raw in path.read_text().splitlines():
            line = raw.strip()
            header = re.match(r"^#\s*TOOL\s+\d+:\s*([A-Za-z0-9_]+)\s*-", line)
            if header:
                names.add((path.name, header.group(1)))
            elif re.match(r"^[A-Z*]+\|", line):
                parts = line.split("|")
                if len(parts) >= 3:
                    names.add((path.name, parts[2].strip()))
    return sorted(names)


def _prebuilt_names():
    """Tool function names and every `action == "..."` literal they dispatch on."""
    names = set()
    for path in _PREBUILT_TOOL_FILES:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.endswith("_tool"):
                names.add((path.name, node.name))
            if (
                isinstance(node, ast.Compare)
                and isinstance(node.left, ast.Name)
                and node.left.id == "action"
            ):
                for comparator in node.comparators:
                    if isinstance(comparator, ast.Constant) and isinstance(
                        comparator.value, str
                    ):
                        names.add((path.name, comparator.value))
    return sorted(names)


def test_name_scanner_catches_a_regression():
    assert _name_offences("timeflow_tool") == ["timeflow"]
    assert _name_offences("dsource_link_appdata") == ["appdata"]
    assert _name_offences("get_container_tags") == ["container"]
    assert _name_offences("search_compliance_inventory") == ["inventory"]
    assert _name_offences("search_vdb_inventory_report") == []
    assert _name_offences("timeline_tool") == []


def test_toolset_tool_and_action_names_use_canonical_terms():
    offenders = [
        (source, name, _name_offences(name))
        for source, name in _toolset_names()
        if _name_offences(name)
    ]
    assert not offenders, f"retired terms in toolset names: {offenders}"


def test_prebuilt_tool_and_action_names_use_canonical_terms():
    names = _prebuilt_names()
    assert len(names) > 100, "scanner found suspiciously few names"
    offenders = [
        (source, name, _name_offences(name))
        for source, name in names
        if _name_offences(name)
    ]
    assert not offenders, f"retired terms in pre-built tool names: {offenders}"


# --------------------------------------------------------------------------- #
# Pre-built tool docstrings
# --------------------------------------------------------------------------- #

# Strip what is an identifier rather than prose: paths, URLs, hyphen/dot
# compounds, {placeholders}, snake_case and camelCase names. API identifiers
# (timeflow_id, /toolkits, appdata_source_params) are the DCT contract and
# cannot be renamed here.
_IDENTIFIER_RE = re.compile(
    r"https?://\S+"
    r"|[\w.{}:~%-]*/[\w.{}:~%/-]*"
    r"|\w+(?:[-.]\w+)+"
    r"|\{[^{}]*\}"
    r"|\w*_\w*"
    r"|\b[a-z]+[A-Z]\w*"
)

# Prose that contains a banned word with a different, legitimate meaning.
_PROSE_EXCEPTIONS = [
    # Oracle's own multitenant terminology (CDB), not the retired Self-Service
    # "container".
    r"container (database|db)s?\b",
    r"virtual container db",
    r"cdb container",
    r"nologging operations on this container",
    r"container type of this\b",
    r"container d\.\.\.",  # "container database", truncated by the generator
    # Continuous Data report listing VDBs, not a Continuous Compliance rule set.
    r"vdb inventory report",
]

# A line that deliberately lists legacy words so the model maps them to the
# canonical term (the per-tool synonym map). Nothing else may quote them.
_ALIAS_LINE = "Customer aliases (accept as input, never use in answers):"


def _docstring_prose():
    for path in _PREBUILT_TOOL_FILES:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            doc = ast.get_docstring(node, clean=False)
            if not doc:
                continue
            for line in doc.splitlines():
                if _ALIAS_LINE in line:
                    continue
                prose = _IDENTIFIER_RE.sub(" ", line).lower()
                for allowed in _PROSE_EXCEPTIONS:
                    prose = re.sub(allowed, " ", prose)
                yield path.name, node.name, line.strip(), prose


def test_docstring_scanner_catches_a_regression():
    prose = _IDENTIFIER_RE.sub(" ", "Unified tool for TIMEFLOW operations.").lower()
    assert re.search(r"\btimeflow\b", prose)
    prose = _IDENTIFIER_RE.sub(" ", "timeflow_id (str): ID of the timeline").lower()
    assert not re.search(r"\btimeflow\b", prose)


@pytest.mark.parametrize("term", _BANNED)
def test_prebuilt_docstrings_are_free_of_internal_terms(term):
    offenders = [
        f"{source}:{func}: {line[:120]}"
        for source, func, line, prose in _docstring_prose()
        if re.search(rf"\b{term}\b", prose)
    ]
    assert not offenders, f"{term!r} leaks in pre-built docstrings: {offenders}"


def test_alias_lines_are_the_only_place_legacy_words_are_quoted():
    """The synonym-map lines must actually exist where the renames happened."""
    text = "\n".join(p.read_text() for p in _PREBUILT_TOOL_FILES)
    for legacy in ('"timeflow"', '"toolkit"', '"database template"', '"container"'):
        assert any(
            _ALIAS_LINE in line and legacy in line for line in text.splitlines()
        ), f"no customer-alias line maps {legacy}"
