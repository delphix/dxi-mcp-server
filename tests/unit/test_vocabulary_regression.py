"""Guard against internal terminology re-entering user-facing text (PPM-1129).

These assert on the *shipped config and message templates* — the strings a user
can actually be shown. They are deliberately cheap so that a future rule or
prompt added with the wrong vocabulary fails at merge time rather than in front
of a customer.
"""

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
]


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
