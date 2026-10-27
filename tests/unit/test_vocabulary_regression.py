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

# Irregular inflections the suffix rule below cannot derive.
_IRREGULAR = {"rewind": ["rewound"]}


def _term_re(term: str) -> str:
    """
    A pattern for *term* and its common inflections.

    Matching only the bare word let "timeflows", "toolkits", "containers" and
    "rewinding" through. A trailing "y" also inflects as "ies" (inventories).
    Hyphens are word boundaries, so a compound such as "timeflow-specific"
    or "AppData-style" is caught by its banned half.
    """
    words = term.split()
    last = words[-1]
    if last.endswith("y"):
        last = rf"{re.escape(last[:-1])}(?:y|ies)"
    else:
        last = rf"{re.escape(last)}(?:s|es|ed|ing|er|ers)?"
    stem = r"\s+".join([re.escape(w) for w in words[:-1]] + [last])
    alternatives = [stem] + [re.escape(w) for w in _IRREGULAR.get(term, [])]
    return rf"\b(?:{'|'.join(alternatives)})\b"


_SRC = Path(__file__).resolve().parents[2] / "src/dct_mcp_server"
_PREBUILT_TOOL_FILES = sorted((_SRC / "tools").glob("*_endpoints_tool.py"))


def _rule_messages():
    return [r.get("message", "") for r in load_manual_confirmation_rules()]


@pytest.mark.parametrize("term", _BANNED)
def test_no_confirmation_message_uses_internal_term(term):
    offenders = [m for m in _rule_messages() if re.search(_term_re(term), m, re.I)]
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
    # Identifier separators become spaces so _term_re's word boundaries and
    # inflections apply ("search_timeflows", "list_toolkits").
    words = " ".join(re.split(r"[_\-\s]+", cleaned))
    return [
        term
        for term in _NAME_BANNED
        if re.search(_term_re(term), words)
        or re.search(_term_re(term.replace(" ", "")), words)
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
    # Inflected forms.
    assert _name_offences("search_timeflows") == ["timeflow"]
    assert _name_offences("list_toolkits") == ["toolkit"]
    assert _name_offences("search_compliance_inventories") == ["inventory"]


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
#
# A hyphenated compound of plain words ("timeflow-specific", "AppData-style")
# is prose, not an identifier: it is deliberately NOT stripped, so the banned
# half of the compound is still checked. Only compounds carrying a digit or a
# dot (tf-1, v1.2, com.delphix.toolkit) are treated as identifiers.
_IDENTIFIER_RE = re.compile(
    r"https?://\S+"
    r"|[\w.{}:~%-]*[/\\][\w.{}:~%/\\-]*"
    r"|\w+(?:\.\w+)+"
    r"|[\w-]*\d[\w-]*-[\w-]*|[\w-]+-[\w-]*\d[\w-]*"
    r"|\{[^{}]*\}"
    r"|`[^`]*`"
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
    # The two leaks the bare-word scanner missed.
    for leak, term in (
        ("commands to execute after rewinding the VDB", "rewind"),
        ("identifier for timeflow-specific TDE objects", "timeflow"),
        ("an AppData-style connector", "appdata"),
        ("all toolkits on the host", "toolkit"),
        ("the VDB was rewound", "rewind"),
    ):
        prose = _IDENTIFIER_RE.sub(" ", leak).lower()
        assert re.search(_term_re(term), prose), leak
    # Identifiers are still stripped.
    for ident in ("tf-1", "com.delphix.toolkit", "/timeflows/{id}", "C:\\toolkit\\bin"):
        assert not re.search(_term_re("timeflow"), _IDENTIFIER_RE.sub(" ", ident))
        assert not re.search(_term_re("toolkit"), _IDENTIFIER_RE.sub(" ", ident))


@pytest.mark.parametrize("term", _BANNED)
def test_prebuilt_docstrings_are_free_of_internal_terms(term):
    offenders = [
        f"{source}:{func}: {line[:120]}"
        for source, func, line, prose in _docstring_prose()
        if re.search(_term_re(term), prose)
    ]
    assert not offenders, f"{term!r} leaks in pre-built docstrings: {offenders}"


def test_alias_lines_are_the_only_place_legacy_words_are_quoted():
    """The synonym-map lines must actually exist where the renames happened."""
    text = "\n".join(p.read_text() for p in _PREBUILT_TOOL_FILES)
    for legacy in ('"timeflow"', '"toolkit"', '"database template"', '"container"'):
        assert any(
            _ALIAS_LINE in line and legacy in line for line in text.splitlines()
        ), f"no customer-alias line maps {legacy}"


# --------------------------------------------------------------------------- #
# GAP-2: dynamic-mode docstrings and elicitation text (S31, S32, S33)
# --------------------------------------------------------------------------- #

_DYNAMIC_PY = (
    Path(__file__).resolve().parents[2] / "src/dct_mcp_server/tools/core/dynamic.py"
)


def _dynamic_tool_prose() -> list[tuple[str, str]]:
    """Yield (func_name, docstring_line) for ``discovery`` and ``execute``."""
    source = _DYNAMIC_PY.read_text()
    tree = ast.parse(source)
    results = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in ("discovery", "execute"):
            continue
        doc = ast.get_docstring(node, clean=False)
        if not doc:
            continue
        for line in doc.splitlines():
            prose = _IDENTIFIER_RE.sub(" ", line).lower()
            results.append((node.name, prose))
    return results


def _elicitation_prose() -> list[tuple[str, str]]:
    """Yield (location, prose) for every string literal inside elicitation schemas.

    Covers ``_CONFIRM_FIELD``, ``_RESOURCE_NAME_FIELD``, ``_ACK_IMPACT_FIELD``,
    and elicitation schema class docstrings — the text the MCP client shows the
    user during the confirmation flow.
    """
    source = _DYNAMIC_PY.read_text()
    tree = ast.parse(source)
    results = []

    # Walk every Constant (string literal) that is a direct child of a
    # call to ``Field(...)`` or the field of a Pydantic BaseModel.
    for node in ast.walk(tree):
        # Field(description=...) literals
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            if func_name == "Field":
                for kw in node.keywords:
                    if kw.arg == "description" and isinstance(kw.value, ast.Constant):
                        prose = _IDENTIFIER_RE.sub(" ", str(kw.value.value)).lower()
                        results.append(("Field.description", prose))
        # Docstrings of elicitation schema classes
        if isinstance(node, ast.ClassDef) and "Schema" in node.name:
            doc = ast.get_docstring(node, clean=False)
            if doc:
                for line in doc.splitlines():
                    prose = _IDENTIFIER_RE.sub(" ", line).lower()
                    results.append((node.name, prose))

    return results


@pytest.mark.parametrize("term", _BANNED)
def test_dynamic_docstrings_are_free_of_internal_terms(term):
    """S31: discovery/execute docstrings must not contain retired Delphix terms."""
    offenders = [
        f"{func}: {prose[:120]}"
        for func, prose in _dynamic_tool_prose()
        if re.search(_term_re(term), prose)
    ]
    assert not offenders, f"{term!r} leaks in dynamic tool docstrings: {offenders}"


@pytest.mark.parametrize("term", _BANNED)
def test_elicitation_text_is_free_of_internal_terms(term):
    """S32: Elicitation schema strings shown to the user must be jargon-free."""
    offenders = [
        f"{loc}: {prose[:120]}"
        for loc, prose in _elicitation_prose()
        if re.search(_term_re(term), prose)
    ]
    assert not offenders, f"{term!r} leaks in elicitation text: {offenders}"


def test_dynamic_docstring_scanner_catches_a_regression():
    """S33: Verify the scanner picks up injected banned terms in a synthetic docstring."""
    # Simulate a docstring line with a banned term
    sample_prose = _IDENTIFIER_RE.sub(" ", "Retrieves the timeflow for a VDB").lower()
    assert re.search(_term_re("timeflow"), sample_prose), (
        "Scanner failed to detect 'timeflow' — the dynamic docstring check is broken"
    )
    # And a clean line passes
    clean_prose = _IDENTIFIER_RE.sub(
        " ", "Returns the current timeline for a VDB"
    ).lower()
    assert not re.search(_term_re("timeflow"), clean_prose)


# --------------------------------------------------------------------------- #
# GAP-6: editorial guidelines cover dynamic-docstring scan (S43)
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# S29: every FR-005 rename registered under new name only, documented old→new
# --------------------------------------------------------------------------- #

# FR-005 rename table: (old_name, new_name).  Hard-coded so any future revert
# immediately breaks this test rather than silently passing with a stale set.
_RENAMES = [
    ("timeflow_tool", "timeline_tool"),
    ("toolkit_tool", "connector_schema_tool"),
    ("database_template_tool", "vdb_template_tool"),
    ("upload_toolkit", "upload_connector_schema"),
    ("delete_toolkit", "delete_connector_schema"),
    ("dsource_link_appdata", "dsource_link_connector"),
    ("dsource_link_appdata_defaults", "dsource_link_connector_defaults"),
    ("update_appdata_dsource", "update_connector_dsource"),
    ("switch_vdb_timeflow", "switch_vdb_timeline"),
    ("switch_timeflow", "switch_timeline"),
    ("create_appdata_source", "create_connector_source"),
    ("update_appdata_source", "update_connector_source"),
    ("get_snapshot_timeflow_range", "get_snapshot_timeline_range"),
    ("get_timeflow_range", "get_timeline_range"),
    ("check_database_connectivity", "check_connectivity"),
]

_PROPOSAL_DOC = (
    Path(__file__).resolve().parents[2]
    / "docs/PPM-1129/PPM-1129-agent-ready-api-surface-proposal.md"
)
_TOOLSETS_DIR = _SRC / "config/toolsets"


def _all_toolset_identifiers() -> set[str]:
    """Collect all tool names (from # TOOL headers) and action names (third column)
    from every config/toolsets/*.txt file."""
    names: set[str] = set()
    for path in sorted(_TOOLSETS_DIR.glob("*.txt")):
        for raw in path.read_text().splitlines():
            line = raw.strip()
            header = re.match(r"^#\s*TOOL\s+\d+:\s*([A-Za-z0-9_]+)\s*-", line)
            if header:
                names.add(header.group(1))
            elif re.match(r"^[A-Z*]+\|", line):
                parts = line.split("|")
                if len(parts) >= 3:
                    names.add(parts[2].strip())
    return names


def test_persona_renames_are_complete_and_documented():
    """S29: every FR-005 rename must be registered under its *new* name only
    and documented old-to-new in the proposal doc.

    Three assertions:
    1. new_name is present in at least one config/toolsets/*.txt file (as a
       TOOL header or as an action name in column 3).
    2. old_name is absent from every toolsets/*.txt file in column 3 / TOOL headers
       (note: the unchanged DCT API path column may still contain the old word;
       that is intentional per NG3 and is not checked here).
    3. Both old_name and new_name appear in the proposal doc's rename table.
    """
    toolset_ids = _all_toolset_identifiers()
    proposal_text = _PROPOSAL_DOC.read_text()

    missing_new: list[str] = []
    present_old: list[str] = []
    undocumented: list[tuple[str, str]] = []

    for old_name, new_name in _RENAMES:
        if new_name not in toolset_ids:
            missing_new.append(new_name)
        if old_name in toolset_ids:
            present_old.append(old_name)
        if old_name not in proposal_text or new_name not in proposal_text:
            undocumented.append((old_name, new_name))

    assert not missing_new, (
        f"New names not found in any config/toolsets/*.txt: {missing_new}"
    )
    assert not present_old, (
        f"Old names still present in config/toolsets/*.txt: {present_old}"
    )
    assert not undocumented, (
        f"Rename pairs not in PPM-1129-agent-ready-api-surface-proposal.md: {undocumented}"
    )


# --------------------------------------------------------------------------- #
# GAP-6: editorial guidelines cover dynamic-docstring scan (S43)
# --------------------------------------------------------------------------- #


def test_editorial_guidelines_mention_dynamic_docstring_scan():
    """S43: vocabulary-editorial-guidelines.md must document the GAP-2 scan.

    When the guidelines were written (PPM-1129 pre-GAP phase), they only listed
    the toolset .txt files and pre-built module docstrings as surfaces to check.
    GAP-2 adds dynamic.py's discovery/execute docstrings and elicitation text as
    a third surface. The guidelines must be updated to prevent future regressions
    by omission.
    """
    guidelines = (
        Path(__file__).resolve().parents[2]
        / ".claude/rules/vocabulary-editorial-guidelines.md"
    )
    text = guidelines.read_text()
    # The guidelines must mention dynamic-mode docstrings or elicitation text
    # as a surface that requires vocabulary review.
    assert any(
        phrase in text.lower()
        for phrase in ("dynamic", "elicitation", "discovery", "execute")
    ), (
        "vocabulary-editorial-guidelines.md does not mention the dynamic-mode "
        "docstring / elicitation surface (GAP-2). Add a row to the 'Where a "
        "vocabulary rule belongs' table."
    )
