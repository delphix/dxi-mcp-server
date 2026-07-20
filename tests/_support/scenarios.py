"""
Scenario catalog — parses `.claude/test/testing/<persona>.md` into runnable Scenario
objects for the Claude-driven persona suite (Layer 5 at full scale).

Each persona file is a list of numbered natural-language prompts grouped under bold
tool-section headers:

    **vdb_tool**
    1. Search for all VDBs
    2. Get the details of the first VDB ...
    **vdb_group_tool**
    18. Search for all VDB groups ...

The bold header gives the tool the prompt is expected to drive. The leading verb of
the prompt classifies it read vs mutation (conservative: anything not clearly a read
is treated as a mutation, so it only runs when mutations are explicitly enabled).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# .claude/test/testing/ lives in the REPO (not in the installed package), so derive
# it from this test file — works under both the editable install and the .venv-live
# non-editable install. (tests/_support/scenarios.py -> repo root is parents[2].)
_REPO_ROOT = Path(__file__).resolve().parents[2]
TESTING_DIR = _REPO_ROOT / ".claude" / "test" / "testing"

_HEADER = re.compile(
    r"^\*\*([a-z][a-z0-9_]*)"
)  # **vdb_tool** or **data_tool — VDB operations**
_PROMPT = re.compile(r"^(\d+)\.\s+(.*\S)\s*$")

# Verbs that mean "read only". A prompt whose first word is one of these is a read;
# everything else (provision/create/delete/start/refresh/...) is treated as a mutation.
_READ_VERBS = {
    "search",
    "get",
    "list",
    "find",
    "show",
    "what",
    "which",
    "how",
    "view",
    "count",
    "display",
    "describe",
    "fetch",
    "retrieve",
    "check",
}

# Mutation verbs used to catch COMPOUND read-prefixed prompts, e.g.
# "List the snapshots for that VDB, then refresh it ...". If a read-prefixed prompt
# contains one of these after a "then"/"and"/";"/"," it actually mutates.
_MUTATION_VERBS = {
    "provision",
    "create",
    "delete",
    "remove",
    "start",
    "stop",
    "enable",
    "disable",
    "refresh",
    "rollback",
    "roll back",
    "add",
    "register",
    "unregister",
    "update",
    "abandon",
    "repair",
    "lock",
    "unlock",
    "link",
    "apply",
    "set ",
    "unset",
    "snapshot",
    "purge",
    "import",
    "attach",
    "detach",
    "assign",
    "revoke",
}


@dataclass(frozen=True)
class Scenario:
    persona: str
    num: int
    prompt: str
    tool: str  # expected tool (from the bold section header)
    tier: str  # "read" | "mutation"

    @property
    def id(self) -> str:
        return f"{self.persona}-{self.num}"


def _classify(prompt: str) -> str:
    p = prompt.lower()
    first = re.sub(r"[^a-z]", "", p.split(" ", 1)[0])
    if first not in _READ_VERBS:
        return "mutation"
    # Compound read-prefixed prompt that then mutates (e.g. "List ... then refresh it").
    # Look past the first clause for a mutation verb.
    tail = re.split(r"\bthen\b|\band\b|;|,", p, maxsplit=1)
    if len(tail) > 1 and any(v in tail[1] for v in _MUTATION_VERBS):
        return "mutation"
    return "read"


@lru_cache(maxsize=None)
def load_scenarios(persona: str) -> tuple:
    """Parse testing/<persona>.md into a tuple of Scenario (cached)."""
    path = TESTING_DIR / f"{persona}.md"
    if not path.exists():
        raise FileNotFoundError(f"no scenario file for persona {persona!r}: {path}")

    scenarios: list[Scenario] = []
    current_tool = None
    for raw in path.read_text().splitlines():
        line = raw.strip()
        h = _HEADER.match(line)
        if h:
            current_tool = h.group(1)
            continue
        m = _PROMPT.match(line)
        if m and current_tool:
            num, prompt = int(m.group(1)), m.group(2)
            scenarios.append(
                Scenario(persona, num, prompt, current_tool, _classify(prompt))
            )
    return tuple(scenarios)


def persona_files() -> list[str]:
    """Personas that have a scenario (.md) file."""
    return sorted(p.stem for p in TESTING_DIR.glob("*.md"))
